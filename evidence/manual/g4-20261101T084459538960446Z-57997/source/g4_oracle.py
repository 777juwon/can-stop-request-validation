"""G4의 A/RX_TIMEOUT 한 번을 원시 관측으로 판정한다.

SUT의 인코더, 상태 판정과 fixture 생성기를 가져오지 않는다. 이 연결 검사는
T-03의 최소 실행이며 B 방식이나 본시험 80회의 실행 결과를 뜻하지 않는다.
"""

from __future__ import annotations

import math
import sys
from collections import defaultdict, deque


SCOPE = "G4_A_RX_TIMEOUT_MINIMUM_CHAIN_ONLY"
PERIOD_NS = 50_000_000
STEP = 0.05


def _integer(value):
    return type(value) is int and value >= 0


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _held(rows, predicate, count):
    """연속 frame과 시뮬레이션 간격으로 유지 구간을 구한다."""
    streak = []
    for row in rows:
        if not predicate(row):
            streak = []
            continue
        if streak and (row["frame"] != streak[-1]["frame"] + 1
                       or abs(row["simulation_time_s"] - streak[-1]["simulation_time_s"] - STEP) > 1e-6):
            streak = []
        streak.append(row)
        if len(streak) >= count:
            return {"first_frame": streak[0]["frame"], "last_frame": row["frame"],
                    "first_simulation_time_s": streak[0]["simulation_time_s"],
                    "last_simulation_time_s": row["simulation_time_s"],
                    "sample_count": len(streak),
                    "observed_span_s": row["simulation_time_s"] - streak[0]["simulation_time_s"]}
    return None


def evaluate_g4(metadata, input_events, can_observer, sut_events,
                adapter_rx, adapter_events, vehicle_states):
    """입력, 독립 요청 관측, 호출과 실제 차속을 각각 대조한다.

    완료 선언 뒤 누락된 자료는 FAIL이다. 중단/환경 오류의 부족한 자료는
    INCONCLUSIVE로 두되 이미 확인된 바이트 오류, 기한 초과와 잠금 해제는 보존한다.
    """
    failures, missing = [], []
    metrics = {"main_comparison_runs_executed": 0, "variant": "A", "scenario": "T-03"}
    complete = metadata.get("execution_status") == "COMPLETE"
    source_complete = metadata.get("fixture_sends_complete") is True
    window_complete = metadata.get("observation_window_complete") is True

    def fail(domain, code, **details):
        failures.append({"domain": domain, "code": code, **details})

    def absent(domain, code, *, definite=None, **details):
        (failures if (complete if definite is None else definite) else missing).append(
            {"domain": domain, "code": code, **details})

    def fields(domain, row, names, code):
        unavailable = [key for key in names if key not in row]
        if unavailable:
            absent(domain, code, fields=unavailable)
        return not unavailable

    token, actor, coordinator = (metadata.get(key) for key in ("run_token", "actor_id", "coordinator_pid"))
    for key, value, maximum, domain in (("run_token", token, 0xFFFFFFFF, "transport"),
                                       ("actor_id", actor, None, "motion"),
                                       ("coordinator_pid", coordinator, None, "transport")):
        if value is None:
            absent(domain, "metadata_missing", field=key)
        elif not _integer(value) or (maximum is not None and value > maximum) or (maximum is None and value == 0):
            fail(domain, "metadata_invalid", field=key)
    valid_token = _integer(token) and token <= 0xFFFFFFFF
    workers = metadata.get("worker_pids")
    workers = workers if isinstance(workers, dict) else {}
    pids = [coordinator] + [workers.get(role) for role in ("sender", "observer", "controller")]
    if not all(_integer(pid) and pid > 0 for pid in pids):
        absent("transport", "four_process_identities_missing")
    elif len(set(pids)) != 4:
        fail("transport", "four_processes_not_independent")

    def stamp(key, domain="transport"):
        value = metadata.get(key)
        if value is None:
            absent(domain, "metadata_time_missing", field=key)
        elif not _integer(value):
            fail(domain, "metadata_time_invalid", field=key)
            return None
        return value

    t0, t0_done, end = (stamp(key) for key in ("t0_ns", "t0_done_ns", "trial_end_ns"))
    active = stamp("adapter_active_ns", "adapter")
    trial_global = metadata.get("trial_global_slot")
    if trial_global is None:
        absent("transport", "trial_global_slot_missing")
    elif not _integer(trial_global) or trial_global % 256 != 0:
        fail("transport", "trial_global_slot_invalid")
    first_due = metadata.get("trial_first_scheduled_ns", t0)
    if t0 is not None and end is not None and end != t0 + 20_000_000_000:
        fail("transport", "trial_duration_invalid")
    if t0 is not None and first_due != t0:
        fail("transport", "trial_schedule_origin_invalid")
    armed = metadata.get("armed")
    arm = armed.get("host_monotonic_ns") if isinstance(armed, dict) else None
    if arm is None:
        absent("request", "explicit_arm_missing")
    elif not _integer(arm):
        fail("request", "explicit_arm_time_invalid")
        arm = None
    if arm is not None and active is not None and active < arm:
        fail("adapter", "adapter_active_before_arm")
    if active is not None and t0 is not None and active > t0:
        fail("adapter", "adapter_active_after_trial_start")

    def raw(row, domain, decoded=True):
        try:
            value = bytes.fromhex(row.get("raw_frame_hex", ""))
        except (TypeError, ValueError):
            value = b""
        if len(value) != 16:
            fail(domain, "raw_frame_length_or_encoding")
            return None
        can_id = int.from_bytes(value[:4], sys.byteorder)
        if can_id not in (0x100, 0x101, 0x200) or value[4:8] != b"\x08\x00\x00\x00":
            fail(domain, "raw_id_dlc_or_flags_invalid")
            return None
        if valid_token and int.from_bytes(value[12:16], "little") != token:
            fail(domain, "raw_run_token_mismatch")
        if decoded:
            expected = {"arbitration_id": can_id, "dlc": 8, "extended": False,
                        "remote": False, "error_frame": False, "data_hex": value[8:].hex()}
            if fields(domain, row, expected, "decoded_fields_missing"):
                if any(type(row[key]) is not type(val) or row[key] != val for key, val in expected.items()):
                    fail(domain, "raw_decoded_disagreement")
        return {**row, "_raw": value, "_id": can_id, "_payload": value[8:]}

    def records(items, domain, event, pid, *, decoded=True, timed=True):
        rows = []
        last = None
        for row in items:
            if not isinstance(row, dict):
                fail(domain, "non_object_log_record")
                continue
            if row.get("event") != event:
                continue
            parsed = raw(row, domain, decoded)
            if parsed is None:
                continue
            if pid is not None and row.get("pid") != pid:
                fail(domain, "process_identity_mismatch", expected_pid=pid)
            if timed:
                when = row.get("host_monotonic_ns")
                if not _integer(when):
                    absent(domain, "receive_time_missing_or_invalid")
                    continue
                if last is not None and when < last:
                    fail(domain, "receive_time_order_invalid")
                last = when
            rows.append(parsed)
        return rows

    sent = records(input_events, "transport", "tx", workers.get("sender"), timed=False)
    obs = records(can_observer, "transport", "rx", workers.get("observer"))
    requests = records(sut_events, "request", "request_tx", workers.get("controller"), timed=False)
    received = records(adapter_rx, "adapter", "rx", coordinator)
    events = records(adapter_events, "adapter", "request", None, decoded=False, timed=False)
    if any(row["_id"] == 0x200 for row in sent):
        fail("transport", "input_sender_sent_request")
    if any(row["_id"] != 0x200 for row in requests):
        fail("request", "controller_sent_non_request")
    if any(row["_id"] != 0x200 for row in received + events):
        fail("adapter", "adapter_non_request_record")
    metrics.update(input_sent_frames=len(sent), observed_frames=len(obs),
                   controller_request_frames=len(requests), adapter_received_frames=len(received),
                   adapter_event_count=len(events))

    # 준비 순번과 본 구간 순번은 같은 전역 슬롯에서 이어져야 한다.
    trial = {}
    prep, schedule_origin, previous_send = [], None, None
    order_by_id = defaultdict(list)
    for row in sent:
        names = ("phase", "global_slot", "slot", "scheduled_ns", "s_begin_ns", "s_done_ns", "bytes_sent")
        if not fields("transport", row, names, "sender_fields_missing"):
            continue
        if not all(_integer(row[key]) for key in ("global_slot", "scheduled_ns", "s_begin_ns", "s_done_ns", "bytes_sent")):
            fail("transport", "sender_timing_invalid")
            continue
        global_slot, phase, slot = row["global_slot"], row["phase"], row["slot"]
        counter = global_slot % 256
        expected_payload = ((b"\xe8\x03" + bytes((counter, 1))) if row["_id"] == 0x100
                            else bytes((counter, 0, 0, 0)))
        if valid_token and row["_payload"] != expected_payload + token.to_bytes(4, "little"):
            fail("transport", "input_literal_fixture_mismatch", global_slot=global_slot)
        if (not row["scheduled_ns"] <= row["s_begin_ns"] < row["scheduled_ns"] + PERIOD_NS
                or row["s_done_ns"] < row["s_begin_ns"] or row["bytes_sent"] != 16
                or (previous_send is not None and row["s_begin_ns"] < previous_send)):
            fail("transport", "sender_time_or_completion_invalid", global_slot=global_slot)
        previous_send = row["s_begin_ns"]
        order_by_id[row["_id"]].append(global_slot)
        if phase == "prepare":
            prep.append(row)
            if slot is not None or (_integer(trial_global) and global_slot >= trial_global):
                fail("transport", "preparation_slot_invalid", global_slot=global_slot)
            this_origin = row["scheduled_ns"] - global_slot * PERIOD_NS
            if schedule_origin is not None and schedule_origin != this_origin:
                fail("transport", "preparation_schedule_invalid")
            schedule_origin = this_origin
        elif phase == "trial":
            if not _integer(slot) or slot >= 400:
                fail("transport", "trial_slot_invalid")
                continue
            key = (row["_id"], slot)
            if key in trial:
                fail("transport", "duplicate_trial_input", arbitration_id=row["_id"], slot=slot)
            trial[key] = row
            if (_integer(trial_global) and global_slot != trial_global + slot) or counter != slot % 256:
                fail("transport", "trial_counter_discontinuity", slot=slot)
            if t0 is not None and row["scheduled_ns"] != t0 + slot * PERIOD_NS:
                fail("transport", "trial_schedule_invalid", slot=slot)
            if row["_id"] == 0x100 and 100 <= slot <= 159:
                fail("transport", "distance_sent_during_interruption", slot=slot)
        else:
            fail("transport", "sender_phase_invalid")
    for can_id, order in order_by_id.items():
        if any(right <= left for left, right in zip(order, order[1:])):
            fail("transport", "input_global_slot_order_invalid", arbitration_id=can_id)
    expected_slots = {(0x101, n) for n in range(400)} | {(0x100, n) for n in range(400) if not 100 <= n <= 159}
    if set(trial) != expected_slots:
        absent("transport", "trial_fixture_incomplete", definite=complete or source_complete,
               expected=740, observed=len(trial), missing_count=len(expected_slots - set(trial)))
    zero = trial.get((0x100, 0))
    if zero is not None and ((t0 is not None and zero.get("s_begin_ns") != t0)
                             or (t0_done is not None and zero.get("s_done_ns") != t0_done)):
        fail("transport", "trial_t0_actual_send_disagreement")

    def match(sources, observations, domain, label, source_time, *, finished=None):
        queues = defaultdict(deque)
        for source in sources:
            queues[source["_raw"]].append(source)
        pairs, previous = [], {}
        for observed in observations:
            queue = queues[observed["_raw"]]
            if not queue:
                absent(domain, label + "_without_matching_source", definite=complete)
                continue
            source = queue.popleft()
            start = source.get(source_time)
            when = observed.get("host_monotonic_ns")
            if not _integer(start):
                absent(domain, label + "_source_time_missing")
            elif _integer(when) and when < start:
                fail(domain, label + "_precedes_source")
            key = source["_id"]
            if _integer(start) and key in previous and start < previous[key]:
                fail(domain, label + "_source_order_invalid")
            if _integer(start):
                previous[key] = start
            pairs.append((source, observed))
        unmatched = sum(len(queue) for queue in queues.values())
        if unmatched:
            absent(domain, label + "_missing", definite=complete if finished is None else finished, count=unmatched)
        return pairs

    input_obs = [row for row in obs if row["_id"] in (0x100, 0x101)]
    input_pairs = match(sent, input_obs, "transport", "independent_input_observation", "s_begin_ns",
                        finished=complete or (source_complete and window_complete))
    if arm is not None:
        arm_inputs = [(source, seen) for source, seen in input_pairs if source["_id"] == 0x100
                      and _integer(source.get("s_done_ns")) and source["s_done_ns"] <= arm
                      and seen["host_monotonic_ns"] <= arm]
        metrics["normal_distance_frames_before_arm"] = len(arm_inputs)
        if len(arm_inputs) < 5:
            absent("request", "five_independent_normal_inputs_before_arm_missing")

    # 요청 생성 로그는 독립 observer의 원시 요청과 일대일 대조할 때만 근거다.
    previous_counter, previous_request = None, None
    for row in requests:
        if not fields("request", row, ("s_begin_ns", "s_done_ns", "bytes_sent"), "request_send_timing_missing"):
            continue
        if (not all(_integer(row[key]) for key in ("s_begin_ns", "s_done_ns", "bytes_sent"))
                or row["s_done_ns"] < row["s_begin_ns"] or row["bytes_sent"] != 16):
            fail("request", "request_send_timing_invalid")
            continue
        payload = row["_payload"]
        if payload[0] not in (0, 1) or payload[1] not in (0, 2, 4) or payload[3] != 0:
            fail("request", "request_literal_contract_invalid")
        if previous_counter is not None and payload[2] != (previous_counter + 1) % 256:
            fail("request", "request_counter_discontinuity")
        if previous_request is not None and row["s_begin_ns"] < previous_request:
            fail("request", "request_send_order_invalid")
        previous_counter, previous_request = payload[2], row["s_begin_ns"]
    observed_requests = [row for row in obs if row["_id"] == 0x200]
    request_pairs = match(requests, observed_requests, "request", "independent_request_observation", "s_begin_ns")
    if not requests:
        absent("request", "controller_request_evidence_missing")
    if not observed_requests:
        absent("request", "independent_request_evidence_missing")
    first_timeout = None
    normal_prefix, init_prefix = [], []
    for source, seen in request_pairs:
        when, sent_at = seen["host_monotonic_ns"], source.get("s_begin_ns")
        if not _integer(sent_at):
            continue
        stop, reason = seen["_payload"][:2]
        if arm is not None and sent_at < arm:
            init_prefix.append(seen)
            if (stop, reason) != (1, 4):
                fail("request", "initial_inhibit_request_invalid")
            continue
        if arm is None and (stop, reason) == (1, 4):
            init_prefix.append(seen)
            continue
        if (stop, reason) == (0, 0):
            if first_timeout is not None:
                fail("request", "stop_request_released_after_timeout")
            normal_prefix.append(seen)
        elif (stop, reason) == (1, 2):
            if first_timeout is None and (end is None or sent_at < end):
                first_timeout = (source, seen)
        else:
            fail("request", "post_arm_request_reason_invalid", stop=stop, reason=reason)
    if not init_prefix:
        absent("request", "initial_inhibit_observation_missing")
    if t0 is not None and not any(row["host_monotonic_ns"] >= t0 for row in normal_prefix):
        absent("request", "normal_trial_prefix_missing")
    last_distance = trial.get((0x100, 99))
    if first_timeout is None:
        absent("request", "timeout_request_not_observed", definite=complete or window_complete)
    elif last_distance is None:
        absent("request", "last_distance_send_missing")
    else:
        source, seen = first_timeout
        low = last_distance.get("s_begin_ns")
        high = last_distance.get("s_done_ns")
        if _integer(low) and _integer(high):
            q_obs = seen["host_monotonic_ns"]
            metrics.update(last_distance_s_begin_ns=low, last_distance_s_done_ns=high,
                           first_timeout_q_obs_ns=q_obs,
                           timeout_observation_after_send_done_ms=(q_obs - high) / 1e6)
            if q_obs < low + 200_000_000:
                fail("request", "timeout_request_before_200ms")
            if q_obs > high + 300_000_000:
                fail("request", "timeout_request_after_300ms")
    if end is not None and observed_requests:
        restored = [row for row in observed_requests if t0 is not None
                    and t0 + 8_000_000_000 <= row["host_monotonic_ns"] < end]
        if not restored:
            absent("request", "restored_interval_stop_evidence_missing")
        elif any(tuple(row["_payload"][:2]) != (1, 2) for row in restored):
            fail("request", "restored_interval_stop_not_latched")
        if not any(_integer(source.get("s_begin_ns")) and end - PERIOD_NS <= source["s_begin_ns"] <= end
                   for source, _ in request_pairs):
            absent("request", "request_run_end_observation_missing")
    request_times = [row["s_begin_ns"] for row in requests if _integer(row.get("s_begin_ns"))]
    metrics["max_request_send_gap_ms"] = max((right - left for left, right in
                                               zip(request_times, request_times[1:])), default=0) / 1e6
    metrics["trial_distance_frames"] = sum(can_id == 0x100 for can_id, _ in trial)
    metrics["trial_heartbeat_frames"] = sum(can_id == 0x101 for can_id, _ in trial)

    active_sources = [row for row in requests if active is not None
                      and _integer(row.get("s_begin_ns")) and row["s_begin_ns"] >= active]
    if active is not None and any(row["host_monotonic_ns"] < active for row in received):
        fail("adapter", "adapter_receive_before_active")
    adapter_pairs = match(active_sources, received, "adapter", "adapter_request_receive", "s_begin_ns")
    event_queues = defaultdict(deque)
    for row in events:
        event_queues[row["_raw"]].append(row)
    completed_calls, durations = [], []
    latched, first_reason = False, None
    for source, rx in adapter_pairs:
        if actor is not None and rx.get("actor_id") != actor:
            fail("adapter", "receive_actor_mismatch")
        queue = event_queues[rx["_raw"]]
        if not queue:
            absent("adapter", "matching_adapter_event_missing")
            continue
        event = queue.popleft()
        payload = rx["_payload"]
        request = {"stop": bool(payload[0]), "reason": payload[1], "counter": payload[2],
                   "run_token": int.from_bytes(payload[4:], "little")}
        if ((actor is not None and event.get("actor_id") != actor)
                or event.get("a_rx_ns") != rx["host_monotonic_ns"]):
            fail("adapter", "adapter_receive_event_disagreement")
        if event.get("request") != request:
            fail("adapter", "adapter_request_raw_disagreement")
        if payload[0] and not latched:
            latched, first_reason = True, payload[1]
        if (event.get("stop_latched") is not latched or event.get("first_reason") != first_reason
                or event.get("action") != ("APPLY_FULL_BRAKE" if latched else "KEEP_EXISTING_CONTROL")):
            fail("adapter", "latched_action_or_reason_invalid")
        if not latched:
            if any(key in event for key in ("a_done_ns", "call_begin_ns", "response")) or event.get("call_completed") is True:
                fail("adapter", "unexpected_normal_control_call")
            continue
        names = ("a_rx_ns", "call_begin_ns", "a_done_ns", "response")
        if not fields("adapter", event, names, "control_call_evidence_missing"):
            continue
        rx_ns, begin, done = (event[key] for key in names[:3])
        if not all(_integer(value) for value in (rx_ns, begin, done)) or not rx_ns <= begin <= done:
            fail("adapter", "control_call_time_invalid")
            continue
        durations.append(done - rx_ns)
        if done - rx_ns > PERIOD_NS:
            fail("adapter", "control_call_late", duration_ns=done - rx_ns)
        response = event["response"]
        if (event.get("call_completed") is not True or not isinstance(response, dict)
                or (actor is not None and response.get("actor_id") != actor) or response.get("error") != ""
                or response.get("do_tick_cue") is not False):
            if event.get("interrupted") is True and event.get("call_completed") is False:
                absent("adapter", "control_call_interrupted")
            else:
                fail("adapter", "control_response_invalid")
        else:
            completed_calls.append((source, done))
    if any(event_queues.values()):
        absent("adapter", "adapter_event_without_receive")
    metrics["max_processing_ms"] = max(durations) / 1e6 if durations else None
    if not received:
        absent("adapter", "adapter_receive_evidence_missing")

    samples = []
    for index, row in enumerate(vehicle_states):
        if not isinstance(row, dict):
            fail("motion", "non_object_vehicle_record", index=index)
            continue
        names = ("phase", "frame", "simulation_time_s", "simulation_delta_s", "host_monotonic_ns",
                 "tick_begin_monotonic_ns", "tick_done_monotonic_ns", "actor_id", "velocity_mps", "speed_mps", "applied_control")
        if not fields("motion", row, names, "vehicle_fields_missing"):
            continue
        if actor is not None and row["actor_id"] != actor:
            fail("motion", "vehicle_actor_mismatch", index=index)
        if (not all(_integer(row[key]) for key in ("frame", "host_monotonic_ns", "tick_begin_monotonic_ns", "tick_done_monotonic_ns"))
                or not all(_number(row[key]) for key in ("simulation_time_s", "simulation_delta_s", "speed_mps"))
                or not row["tick_begin_monotonic_ns"] <= row["tick_done_monotonic_ns"] <= row["host_monotonic_ns"]
                or abs(row["simulation_delta_s"] - STEP) > 1e-6):
            fail("motion", "vehicle_clock_invalid", index=index)
            continue
        velocity, control = row["velocity_mps"], row["applied_control"]
        if (not isinstance(velocity, dict) or not all(_number(velocity.get(key)) for key in ("x", "y", "z"))
                or not isinstance(control, dict) or not all(_number(control.get(key)) for key in ("throttle", "brake", "steer"))
                or type(control.get("hand_brake")) is not bool):
            fail("motion", "vehicle_state_invalid", index=index)
            continue
        speed = math.hypot(velocity["x"], velocity["y"])
        if not math.isclose(speed, row["speed_mps"], abs_tol=1e-9, rel_tol=1e-9):
            fail("motion", "reported_velocity_disagreement", frame=row["frame"])
        samples.append({**row, "observed_speed_mps": speed})
    phases = {"settle": 0, "drive": 1, "g4": 2}
    for left, right in zip(samples, samples[1:]):
        delta = right["frame"] - left["frame"]
        if delta != 1:
            absent("motion", "vehicle_frame_gap")
        if (delta <= 0 or abs(right["simulation_time_s"] - left["simulation_time_s"] - delta * STEP) > 1e-6
                or right["host_monotonic_ns"] < left["host_monotonic_ns"]):
            fail("motion", "vehicle_time_discontinuity")
        if phases.get(right["phase"], -1) < phases.get(left["phase"], -1):
            fail("motion", "vehicle_phase_order_invalid")
    if any(row["phase"] not in phases for row in samples):
        fail("motion", "vehicle_phase_invalid")
    drive = [row for row in samples if row["phase"] == "drive" and (t0 is None or row["host_monotonic_ns"] <= t0)]
    stable = _held(drive[-21:], lambda row: 4.5 <= row["observed_speed_mps"] * 3.6 <= 5.5, 21)
    metrics["initial_speed_hold"] = stable
    if stable is None:
        absent("motion", "initial_speed_hold_missing")
    ready = metadata.get("trial_ready")
    ready_row = None
    if not isinstance(ready, dict) or not all(key in ready for key in ("frame", "simulation_time_s", "host_monotonic_ns")):
        absent("motion", "trial_ready_missing")
    elif not (_integer(ready["frame"]) and _integer(ready["host_monotonic_ns"]) and _number(ready["simulation_time_s"])):
        fail("motion", "trial_ready_invalid")
    else:
        ready_row = next((row for row in drive if row["frame"] == ready["frame"]
                          and abs(row["simulation_time_s"] - ready["simulation_time_s"]) <= 1e-6
                          and row["host_monotonic_ns"] == ready["host_monotonic_ns"]), None)
        if ready_row is None:
            absent("motion", "trial_ready_snapshot_not_observed")
        if drive and ready["frame"] != drive[-1]["frame"]:
            fail("motion", "trial_ready_not_last_drive_frame")
        if t0 is not None and ready["host_monotonic_ns"] > t0:
            fail("motion", "trial_ready_after_t0")
    prep_times = [metadata.get(key) for key in ("preparation_started_monotonic_ns", "preparation_deadline_monotonic_ns",
                                              "preparation_completed_monotonic_ns")]
    if not all(_integer(value) for value in prep_times):
        absent("motion", "preparation_metadata_missing_or_invalid")
    else:
        start, deadline, done = prep_times
        metrics["preparation_seconds"] = (done - start) / 1e9
        if (deadline != start + 30_000_000_000 or not start <= done <= deadline
                or (t0 is not None and not done <= t0 <= deadline)
                or (arm is not None and not start <= arm <= done)):
            fail("motion", "preparation_deadline_or_order_invalid")
    g4 = [row for row in samples if row["phase"] == "g4"]
    if t0 is not None and any(row["tick_begin_monotonic_ns"] < t0 for row in g4):
        fail("motion", "g4_observation_precedes_t0")
    # T0를 가로지른 tick도 원래 phase로 보존하므로 전체 frame 연속성을 사용한다.
    if ready_row is not None and g4 and g4[0]["frame"] <= ready_row["frame"]:
        fail("motion", "g4_frame_not_after_trial_ready")

    def braking(row):
        control = row["applied_control"]
        return (control["brake"] >= 0.999 and control["throttle"] <= 0.001
                and abs(control["steer"]) <= 0.001 and not control["hand_brake"])

    first_done = None
    if first_timeout is not None:
        first_source = first_timeout[0]
        first_done = next((done for source, done in completed_calls if source is first_source), None)
    metrics.update(first_brake_applied=None, stop_hold=None)
    if first_done is None:
        absent("motion", "first_timeout_brake_call_missing")
    applied = next((row for row in g4 if first_done is not None
                    and row["tick_begin_monotonic_ns"] >= first_done and braking(row)), None)
    next_tick = next((row for row in g4 if first_done is not None
                      and row["tick_begin_monotonic_ns"] >= first_done), None)
    if next_tick is not None and not braking(next_tick):
        fail("motion", "first_tick_after_brake_call_not_braking", frame=next_tick["frame"])
    metrics["pre_request_full_brake_frames"] = [row["frame"] for row in g4 if first_done is not None
                                              and row["tick_begin_monotonic_ns"] < first_done and braking(row)]
    if applied is None:
        absent("motion", "applied_brake_not_observed", definite=complete or window_complete)
    else:
        metrics["first_brake_applied"] = {key: applied[key] for key in ("frame", "simulation_time_s", "host_monotonic_ns")}
        after = [row for row in g4 if row["frame"] >= applied["frame"]]
        if any(not braking(row) for row in after):
            fail("motion", "latched_brake_not_maintained")
        stopped = _held([row for row in after if row["frame"] <= applied["frame"] + 40],
                        lambda row: row["observed_speed_mps"] <= 0.1 and braking(row), 11)
        metrics["stop_hold"] = stopped
        if stopped is None:
            absent("motion", "stop_hold_not_observed_within_40_frames", definite=complete or window_complete)
        if not after or after[-1]["frame"] < applied["frame"] + 40:
            absent("motion", "motion_window_incomplete", definite=complete or window_complete)
        if stopped:
            metrics["stop_hold_completed_after_applied_frames"] = stopped["last_frame"] - applied["frame"]
    if completed_calls and not any(row["tick_begin_monotonic_ns"] >= max(done for _, done in completed_calls) for row in g4):
        absent("motion", "state_after_last_brake_call_missing", definite=complete or window_complete)
    if end is not None and not any(row["host_monotonic_ns"] >= end for row in g4):
        absent("motion", "vehicle_run_end_observation_missing", definite=complete or window_complete)
    if not any(row["observed_speed_mps"] > 0.1 for row in g4
               if first_timeout is None or row["host_monotonic_ns"] < first_timeout[1]["host_monotonic_ns"]):
        absent("motion", "actual_trial_prefix_motion_missing")

    worker_exits_ok = True
    worker_results = metadata.get("worker_results")
    worker_results = worker_results if isinstance(worker_results, dict) else {}
    for role in ("sender", "observer", "controller"):
        domain = "request" if role == "controller" else "transport"
        exit_code = metadata.get(role + "_exit_code")
        if type(exit_code) is not int or exit_code != 0:
            worker_exits_ok = False
            absent(domain, "worker_exit_not_successful", role=role)
        result = worker_results.get(role)
        if not isinstance(result, dict) or result.get("status") != "COMPLETE":
            worker_exits_ok = False
            absent(domain, "worker_completion_record_missing", role=role)
        if isinstance(result, dict):
            if workers.get(role) is not None and result.get("pid") != workers[role]:
                fail(domain, "worker_result_pid_disagreement", role=role)
            if valid_token and result.get("run_token") != token:
                fail(domain, "worker_result_token_disagreement", role=role)
    if not source_complete:
        absent("transport", "fixture_sends_not_complete")
    if not window_complete:
        absent("motion", "observation_window_not_complete")
    if not complete:
        absent("transport", "execution_not_complete", definite=False)

    def status(domain):
        if any(item["domain"] == domain for item in failures):
            return "FAIL"
        return "INCONCLUSIVE" if any(item["domain"] == domain for item in missing) else "PASS"

    statuses = {domain + "_status": status(domain) for domain in ("transport", "request", "adapter", "motion")}
    return {"scope": SCOPE, "all_checks_passed": complete and source_complete and window_complete and worker_exits_ok
            and all(value == "PASS" for value in statuses.values()), "failures": failures,
            "missing_evidence": missing, "metrics": metrics, **statuses}
