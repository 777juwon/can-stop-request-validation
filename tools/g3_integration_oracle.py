"""G3의 원시 CAN, adapter 호출과 CARLA 관측을 독립적으로 대조한다.

송수신기나 adapter의 pack/parse 함수와 내부 시간 판정을 가져오지 않는다.
이번 20개 연결 fixture만 판정하며 SUT, 거리 이상과 본시험 80회는 다루지 않는다.
이 모듈 자체와 합성 로그의 단위 검사는 실제 통합 실행 증거가 아니다.
"""

from __future__ import annotations

import math
import sys


SCOPE = "G3_CAN_TO_CARLA_INTEGRATION_ONLY"
PERIOD_NS = 50_000_000
STEP = 0.05


def _integer(value):
    return type(value) is int and value >= 0


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _held(rows, predicate, count):
    """0.05초 연속 frame 수로 구간을 확인해 float32 끝 경계를 보존한다."""
    streak = []
    for row in rows:
        contiguous = not streak or (
            row["frame"] == streak[-1]["frame"] + 1
            and abs(row["simulation_time_s"] - streak[-1]["simulation_time_s"] - STEP) <= 1e-6
        )
        if not predicate(row):
            streak = []
            continue
        if not contiguous:
            streak = []
        streak.append(row)
        if len(streak) >= count:
            return {"first_frame": streak[0]["frame"], "last_frame": row["frame"],
                    "first_simulation_time_s": streak[0]["simulation_time_s"],
                    "last_simulation_time_s": row["simulation_time_s"],
                    "sample_count": len(streak),
                    "observed_span_s": row["simulation_time_s"] - streak[0]["simulation_time_s"]}
    return None


def evaluate_integration(metadata, tx, observed, adapter_rx, adapter_events, vehicle_samples):
    """공통 호스트 시각과 서로 다른 관측 근거로 G3 구성 요소를 판정한다.

    완료된 로그의 누락은 실패다. 중단된 실행의 부족한 근거는 미결정으로 두고,
    이미 관측한 잘못된 바이트, 늦은 호출과 제동 해제 등의 실패는 유지한다.
    최상위 gate 상태와 자원 정리는 호출자가 별도로 합친다.
    """
    failures, missing = [], []
    metrics = {"main_comparison_runs_executed": 0}
    complete = metadata.get("execution_status") == "COMPLETE"
    source_complete = metadata.get("fixture_sends_complete") is True
    window_complete = metadata.get("observation_window_complete") is True

    def fail(domain, code, **details):
        failures.append({"domain": domain, "code": code, **details})

    def absent(domain, code, *, definite=False, **details):
        if definite:
            fail(domain, code, **details)
        else:
            missing.append({"domain": domain, "code": code, **details})

    def need_fields(domain, row, fields, code):
        absent_fields = [key for key in fields if key not in row]
        if absent_fields:
            absent(domain, code, definite=complete, fields=absent_fields)
        return not absent_fields

    token, actor, coordinator = (metadata.get(key) for key in ("run_token", "actor_id", "coordinator_pid"))
    for key, value, maximum in (("run_token", token, 0xFFFFFFFF),
                                ("actor_id", actor, None), ("coordinator_pid", coordinator, None)):
        if value is None:
            absent("transport" if key != "actor_id" else "motion", "metadata_missing", definite=complete, field=key)
        elif not _integer(value) or (maximum is not None and value > maximum) or (maximum is None and value == 0):
            fail("transport" if key != "actor_id" else "motion", "metadata_invalid", field=key)
    valid_token = _integer(token) and token <= 0xFFFFFFFF

    def expected_payload(slot):
        # 다른 모듈의 fixture 생성기와 디코더를 사용하지 않는 기대 바이트다.
        stop, reason = (1, 1) if 5 <= slot <= 9 else (0, 0)
        return bytes((stop, reason, slot, 0)) + token.to_bytes(4, "little")

    def raw_slot(row, domain, *, decoded_fields):
        raw_hex = row.get("raw_frame_hex")
        try:
            raw = bytes.fromhex(raw_hex) if isinstance(raw_hex, str) else b""
        except ValueError:
            raw = b""
        if len(raw) != 16:
            fail(domain, "raw_frame_length_or_encoding")
            return None
        slot = raw[10]
        if slot >= 20:
            fail(domain, "raw_counter_outside_fixture", counter=slot)
            return None
        can_id = int.from_bytes(raw[:4], sys.byteorder)
        if can_id != 0x200 or raw[4] != 8:
            fail(domain, "raw_id_dlc_or_flags_invalid", slot=slot)
        if valid_token:
            header = (0x200).to_bytes(4, sys.byteorder) + b"\x08\x00\x00\x00"
            if raw != header + expected_payload(slot):
                fail(domain, "raw_fixture_mismatch", slot=slot)
        if decoded_fields:
            expected = {"arbitration_id": can_id & (0x1FFFFFFF if can_id & 0x80000000 else 0x7FF),
                        "dlc": raw[4], "extended": bool(can_id & 0x80000000),
                        "remote": bool(can_id & 0x40000000), "error_frame": bool(can_id & 0x20000000)}
            if need_fields(domain, row, (*expected, "data_hex"), "decoded_fields_missing"):
                if any(type(row[key]) is not type(value) or row[key] != value for key, value in expected.items()):
                    fail(domain, "raw_decoded_disagreement", slot=slot)
                try:
                    data = bytes.fromhex(row["data_hex"])
                except (TypeError, ValueError):
                    data = None
                if data != raw[8:8 + raw[4]]:
                    fail(domain, "raw_payload_disagreement", slot=slot)
        return slot

    def stream(items, domain, event, *, require_decoded=True, finished=False):
        rows, indexed, order = [], {}, []
        for row in items:
            if not isinstance(row, dict):
                fail(domain, "non_object_log_record")
                continue
            if row.get("event") != event:
                continue
            slot = raw_slot(row, domain, decoded_fields=require_decoded)
            if slot is None:
                continue
            rows.append(row)
            order.append(slot)
            if slot in indexed:
                fail(domain, "duplicate_frame", slot=slot)
            else:
                indexed[slot] = row
        if any(right <= left for left, right in zip(order, order[1:])):
            fail(domain, "frame_order_invalid")
        if set(indexed) != set(range(20)) or len(rows) != 20:
            absent(domain, "fixture_frames_missing", definite=finished,
                   expected=20, observed=len(rows), missing_slots=sorted(set(range(20)) - set(indexed)))
        return rows, indexed

    sent, sent_by_slot = stream(tx, "transport", "tx", finished=source_complete or complete)
    obs, obs_by_slot = stream(observed, "transport", "rx", finished=window_complete and source_complete)
    received, rx_by_slot = stream(adapter_rx, "adapter", "rx", finished=complete)
    events, events_by_slot = stream(adapter_events, "adapter", "request", require_decoded=False, finished=complete)
    metrics.update(sent_frames=len(sent), observed_frames=len(obs), adapter_received_frames=len(received),
                   adapter_event_count=len(events))

    for rows, label in ((sent, "sender"), (obs, "observer"), (received, "adapter")):
        pids = set()
        for row in rows:
            if _integer(row.get("pid")) and row["pid"] > 0:
                pids.add(row["pid"])
            else:
                absent("adapter" if label == "adapter" else "transport", "process_id_missing_or_invalid", definite=complete, role=label)
        metrics[label + "_pids"] = sorted(pids)
        if len(pids) > 1:
            fail("transport" if label != "adapter" else "adapter", "process_identity_changed", role=label)
        if label == "adapter" and pids and pids != {coordinator}:
            fail("adapter", "adapter_not_coordinator")
    sender_pids, observer_pids = set(metrics["sender_pids"]), set(metrics["observer_pids"])
    if sender_pids & observer_pids or coordinator in sender_pids | observer_pids:
        fail("transport", "sender_observer_not_independent")
    recorded_pids = metadata.get("worker_pids")
    if isinstance(recorded_pids, dict):
        for role, pids in (("sender", sender_pids), ("observer", observer_pids)):
            if pids and pids != {recorded_pids.get(role)}:
                fail("transport", "worker_pid_metadata_disagreement", role=role)

    origin = None
    previous_send = None
    for slot, row in sent_by_slot.items():
        fields = ("slot", "scheduled_ns", "s_begin_ns", "s_done_ns", "bytes_sent")
        if not need_fields("transport", row, fields, "sender_timing_missing"):
            continue
        if not all(_integer(row[key]) for key in fields):
            fail("transport", "sender_timing_invalid", slot=slot)
            continue
        this_origin = row["scheduled_ns"] - slot * PERIOD_NS
        origin = this_origin if origin is None else origin
        if (row["slot"] != slot or this_origin != origin
                or not row["scheduled_ns"] <= row["s_begin_ns"] < row["scheduled_ns"] + PERIOD_NS
                or row["s_done_ns"] < row["s_begin_ns"] or row["bytes_sent"] != 16
                or (previous_send is not None and row["s_begin_ns"] < previous_send)):
            fail("transport", "sender_fixture_or_time_invalid", slot=slot)
        previous_send = row["s_begin_ns"]
    for rows, indexed, domain in ((obs, obs_by_slot, "transport"), (received, rx_by_slot, "adapter")):
        previous_rx = None
        for slot, row in indexed.items():
            stamp = row.get("host_monotonic_ns")
            if not _integer(stamp):
                absent(domain, "receive_time_missing_or_invalid", definite=complete, slot=slot)
                continue
            if previous_rx is not None and stamp < previous_rx:
                fail(domain, "receive_time_order_invalid", slot=slot)
            previous_rx = stamp
            source = sent_by_slot.get(slot)
            if source is None or not _integer(source.get("s_begin_ns")):
                absent(domain, "matching_send_missing", definite=complete, slot=slot)
            elif stamp < source["s_begin_ns"]:
                fail(domain, "receive_precedes_send_call", slot=slot)
            if domain == "adapter" and row.get("actor_id") != actor:
                fail(domain, "receive_actor_mismatch", slot=slot)

    durations, completed_calls = [], {}
    for slot, row in events_by_slot.items():
        if row.get("actor_id") != actor:
            fail("adapter", "event_actor_mismatch", slot=slot)
        received_row = rx_by_slot.get(slot)
        if received_row is None:
            absent("adapter", "matching_adapter_receive_missing", definite=complete, slot=slot)
        elif row.get("a_rx_ns") != received_row.get("host_monotonic_ns"):
            fail("adapter", "adapter_receive_event_disagreement", slot=slot)
        expected_request = {"stop": 5 <= slot <= 9, "reason": 1 if 5 <= slot <= 9 else 0,
                            "counter": slot, "run_token": token}
        if row.get("request") != expected_request:
            fail("adapter", "request_raw_disagreement", slot=slot)
        latched = slot >= 5
        if (row.get("stop_latched") is not latched or row.get("first_reason") != (1 if latched else None)
                or row.get("action") != ("APPLY_FULL_BRAKE" if latched else "KEEP_EXISTING_CONTROL")):
            fail("adapter", "latched_action_or_reason_invalid", slot=slot)
        if not latched:
            if any(key in row for key in ("a_done_ns", "call_begin_ns", "response")) or row.get("call_completed") is True:
                fail("adapter", "unexpected_normal_control_call", slot=slot)
            continue
        if row.get("call_completed") is False and row.get("interrupted") is not True:
            fail("adapter", "control_call_failed", slot=slot)
        fields = ("a_rx_ns", "call_begin_ns", "a_done_ns", "response")
        if not need_fields("adapter", row, fields, "control_call_evidence_missing"):
            continue
        rx, begin, done = (row[key] for key in fields[:3])
        if not all(_integer(value) for value in (rx, begin, done)) or not rx <= begin <= done:
            fail("adapter", "control_call_time_invalid", slot=slot)
            continue
        # 내부 진단용 processing_duration_ns/call_within_50ms를 판정에 사용하지 않는다.
        duration = done - rx
        durations.append(duration)
        if duration > 50_000_000:
            fail("adapter", "control_call_late", slot=slot, duration_ns=duration)
        response = row["response"]
        if (not isinstance(response, dict) or response.get("actor_id") != actor
                or response.get("error") != "" or response.get("do_tick_cue") is not False):
            fail("adapter", "control_response_invalid", slot=slot)
        else:
            completed_calls[slot] = done
    metrics["max_processing_ms"] = max(durations) / 1e6 if durations else None

    valid_samples = []
    for index, row in enumerate(vehicle_samples):
        if not isinstance(row, dict):
            fail("motion", "non_object_vehicle_record", index=index)
            continue
        needed = ("phase", "frame", "simulation_time_s", "simulation_delta_s", "host_monotonic_ns",
                  "tick_begin_monotonic_ns", "tick_done_monotonic_ns", "actor_id", "velocity_mps", "speed_mps", "applied_control")
        if not need_fields("motion", row, needed, "vehicle_fields_missing"):
            continue
        if row["actor_id"] != actor:
            fail("motion", "vehicle_actor_mismatch", index=index)
        clock_fields = ("frame", "host_monotonic_ns", "tick_begin_monotonic_ns", "tick_done_monotonic_ns")
        if (not all(_integer(row[key]) for key in clock_fields)
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
        if not math.isclose(row["speed_mps"], speed, abs_tol=1e-9, rel_tol=1e-9):
            fail("motion", "reported_velocity_disagreement", frame=row["frame"])
        valid_samples.append({**row, "observed_speed_mps": speed})
    for left, right in zip(valid_samples, valid_samples[1:]):
        frame_delta = right["frame"] - left["frame"]
        if frame_delta != 1:
            absent("motion", "vehicle_frame_gap", definite=complete, frame=right["frame"])
        if (frame_delta <= 0 or abs(right["simulation_time_s"] - left["simulation_time_s"] - frame_delta * STEP) > 1e-6
                or right["host_monotonic_ns"] < left["host_monotonic_ns"]):
            fail("motion", "vehicle_time_discontinuity", frame=right["frame"])
    phases = {"settle": 0, "drive": 1, "g3": 2}
    if any(row["phase"] not in phases for row in valid_samples) or any(
            phases.get(right["phase"], -1) < phases.get(left["phase"], -1)
            for left, right in zip(valid_samples, valid_samples[1:])):
        fail("motion", "vehicle_phase_order_invalid")

    prep_fields = ("preparation_started_monotonic_ns", "preparation_deadline_monotonic_ns", "preparation_completed_monotonic_ns")
    prep_available = need_fields("motion", metadata, prep_fields, "preparation_metadata_missing")
    prep_values = [metadata.get(key) for key in prep_fields]
    if prep_available and not all(_integer(value) for value in prep_values):
        if any(value is not None and not _integer(value) for value in prep_values):
            fail("motion", "preparation_time_invalid")
        else:
            absent("motion", "preparation_not_completed", definite=complete)
        prep_available = False
    armed = metadata.get("armed")
    armed_available = isinstance(armed, dict) and all(key in armed for key in ("host_monotonic_ns", "frame", "simulation_time_s"))
    if not armed_available:
        absent("motion", "arm_evidence_missing", definite=complete)
    elif not (_integer(armed["host_monotonic_ns"]) and _integer(armed["frame"]) and _number(armed["simulation_time_s"])):
        fail("motion", "arm_evidence_invalid")
        armed_available = False
    drive = [row for row in valid_samples if row["phase"] == "drive"]
    stable = _held(drive, lambda row: 4.5 <= row["observed_speed_mps"] * 3.6 <= 5.5, 21)
    metrics["initial_speed_hold"] = stable
    if stable is None:
        absent("motion", "initial_speed_hold_missing", definite=complete)
    if prep_available:
        start, deadline, done = prep_values
        metrics["preparation_seconds"] = (done - start) / 1e9
        if deadline - start != 30_000_000_000 or not start <= done <= deadline:
            fail("motion", "preparation_deadline_violated")
        if stable is not None:
            last_stable = next(row for row in drive if row["frame"] == stable["last_frame"])
            if not start <= last_stable["host_monotonic_ns"] <= done:
                fail("motion", "speed_hold_outside_preparation")
        if armed_available and armed["host_monotonic_ns"] < done:
            fail("motion", "arm_precedes_preparation")
    if armed_available:
        matches = [row for row in drive if row["frame"] == armed["frame"]
                   and abs(row["simulation_time_s"] - armed["simulation_time_s"]) <= 1e-6]
        if not matches:
            absent("motion", "arm_snapshot_not_observed", definite=complete)
        elif matches[-1]["host_monotonic_ns"] > armed["host_monotonic_ns"]:
            fail("motion", "arm_precedes_snapshot")
        if drive and armed["frame"] != drive[-1]["frame"]:
            fail("motion", "arm_not_last_drive_snapshot")
        if any(_integer(row.get("s_begin_ns")) and row["s_begin_ns"] < armed["host_monotonic_ns"] for row in sent):
            fail("transport", "fixture_sent_before_arm")

    g3 = [row for row in valid_samples if row["phase"] == "g3"]
    if completed_calls and not any(row["tick_begin_monotonic_ns"] >= max(completed_calls.values()) for row in g3):
        absent("motion", "state_after_last_brake_call_missing", definite=complete or window_complete)
    if armed_available and any(row["frame"] <= armed["frame"] or row["tick_begin_monotonic_ns"] < armed["host_monotonic_ns"] for row in g3):
        fail("motion", "g3_observation_precedes_arm")
    moving = any(row["observed_speed_mps"] > 0.1 for row in drive)
    metrics["actual_prefix_motion_observed"] = moving
    if not moving:
        absent("motion", "actual_prefix_motion_missing", definite=complete)

    def braking(row):
        control = row["applied_control"]
        return control["brake"] >= 0.999 and control["throttle"] <= 0.001 and abs(control["steer"]) <= 0.001 and not control["hand_brake"]

    # Ackermann 속도 조절의 이전 제동을 CAN 요청의 적용으로 귀속하지 않는다.
    first_done = completed_calls.get(5)
    applied = next((row for row in g3 if first_done is not None
                    and row["tick_begin_monotonic_ns"] >= first_done and braking(row)), None)
    metrics["pre_request_full_brake_frames"] = [row["frame"] for row in g3
        if first_done is not None and row["tick_begin_monotonic_ns"] < first_done and braking(row)]
    if first_done is None:
        absent("motion", "first_brake_call_missing", definite=complete)
    metrics["first_brake_applied"] = None
    metrics["stop_hold"] = None
    if applied is None:
        absent("motion", "applied_brake_not_observed", definite=window_complete or complete)
    else:
        metrics["first_brake_applied"] = {key: applied[key] for key in ("frame", "simulation_time_s", "host_monotonic_ns")}
        after = [row for row in g3 if row["frame"] >= applied["frame"]]
        if any(not braking(row) for row in after):
            fail("motion", "latched_brake_not_maintained")
        window = [row for row in after if row["frame"] <= applied["frame"] + 40]
        stopped = _held(window, lambda row: row["observed_speed_mps"] <= 0.1 and braking(row), 11)
        metrics["stop_hold"] = stopped
        if stopped is None:
            absent("motion", "stop_hold_not_observed_within_40_frames", definite=window_complete or complete)
        if not after or after[-1]["frame"] < applied["frame"] + 40:
            absent("motion", "motion_window_incomplete", definite=window_complete or complete)
        if stopped:
            metrics["stop_hold_completed_after_applied_frames"] = stopped["last_frame"] - applied["frame"]
    if not window_complete:
        absent("motion", "observation_window_not_complete")
    worker_exits_ok = all(type(metadata.get(key)) is int and metadata[key] == 0
                         for key in ("sender_exit_code", "observer_exit_code"))
    if not worker_exits_ok:
        absent("transport", "worker_exit_not_successful")
    if not source_complete:
        absent("transport", "fixture_sends_not_complete")

    def status(domain):
        if any(item["domain"] == domain for item in failures):
            return "FAIL"
        if any(item["domain"] == domain for item in missing):
            return "INCONCLUSIVE"
        return "PASS"

    statuses = {domain + "_status": status(domain) for domain in ("transport", "adapter", "motion")}
    return {"scope": SCOPE, "all_checks_passed": complete and source_complete and window_complete
            and worker_exits_ok
            and all(value == "PASS" for value in statuses.values()),
            "failures": failures, "missing_evidence": missing, "metrics": metrics, **statuses}
