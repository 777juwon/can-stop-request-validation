"""보존된 두 번째 G4 실행을 표준 라이브러리만으로 다시 계산한다.

SUT, fixture 생성기, 기존 oracle과 result.json의 판정을 가져오지 않는다.
이 파일을 실행하면 같은 폴더에 observation_audit.json을 기록한다.
새 CAN/CARLA 실행, B 방식 검증 또는 본시험 수행을 뜻하지 않는다.
"""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import struct
import sys


BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
PERIOD = 50_000_000
errors = []


def require(condition, code, **detail):
    """실패 근거를 보존하고 나머지 독립 검사를 계속한다."""
    if not condition:
        errors.append({"code": code, **detail})


def read_json(name):
    return json.loads((BASE / name).read_text(encoding="utf-8"))


def read_rows(name):
    return [json.loads(line) for line in (BASE / name).read_text(encoding="utf-8").splitlines() if line]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unpack(row):
    """Classic CAN의 원시 16바이트를 직접 해석한다."""
    data = bytes.fromhex(row["raw_frame_hex"])
    require(len(data) == 16, "raw_length_invalid")
    can_id, dlc, payload = struct.unpack("=IB3x8s", data)
    require(can_id in (0x100, 0x101, 0x200) and dlc == 8
            and data[5:8] == b"\x00\x00\x00", "raw_header_invalid")
    expected = {"arbitration_id": can_id, "dlc": 8, "extended": False,
                "remote": False, "error_frame": False, "data_hex": payload.hex()}
    for key, value in expected.items():
        if key in row:
            require(type(row[key]) is type(value) and row[key] == value,
                    "decoded_field_disagrees_with_raw", field=key)
    require(int.from_bytes(payload[4:], "little") == metadata["run_token"], "raw_token_invalid")
    return can_id, payload


def compare(source, observed, code):
    """ID별 순서를 보존해 원시 바이트와 실제 송신/수신 시각을 대조한다."""
    require(len(source) == len(observed), code + "_count", source=len(source), observed=len(observed))
    for index, (tx, rx) in enumerate(zip(source, observed)):
        require(tx["raw_frame_hex"] == rx["raw_frame_hex"], code + "_raw", index=index)
        require(tx["s_begin_ns"] <= rx["host_monotonic_ns"], code + "_time", index=index)


def full_brake(row):
    control = row["applied_control"]
    return (control["brake"] >= 0.999 and control["throttle"] <= 0.001
            and abs(control["steer"]) <= 0.001 and control["hand_brake"] is False)


metadata = read_json("metadata.json")
inputs = [row for row in read_rows("input_events.jsonl") if row["event"] == "tx"]
omissions = [row for row in read_rows("input_events.jsonl") if row["event"] == "distance_omitted"]
observed = read_rows("can_observer.jsonl")
requests = [row for row in read_rows("sut_events.jsonl") if row["event"] == "request_tx"]
adapter = read_rows("adapter_rx.jsonl")
prearm = read_rows("adapter_prearm_rx.jsonl")
events = read_rows("adapter_events.jsonl")
samples = read_rows("vehicle_states.jsonl")
token, actor = metadata["run_token"], metadata["actor_id"]
t0, end, arm, active = (metadata[key] for key in ("t0_ns", "trial_end_ns", "armed", "adapter_active_ns"))
arm = arm["host_monotonic_ns"]
decoded = {id(row): unpack(row) for row in inputs + observed + requests + adapter + prearm + events}

# 별도 프로세스의 기록과 실제 PID를 서로 대조한다.
pids = {"coordinator": metadata["coordinator_pid"], **metadata["worker_pids"]}
require(len(set(pids.values())) == 4 and all(type(pid) is int and pid > 0 for pid in pids.values()),
        "four_processes_not_independent")
for role in ("sender", "observer", "controller"):
    result = read_json(role + "_result.json")
    ready = read_json(role + "_ready.json")
    require(result["status"] == "COMPLETE" and result["exit_code"] == metadata[role + "_exit_code"] == 0,
            "worker_not_complete", role=role)
    require(result["pid"] == ready["pid"] == pids[role] and result["run_token"] == ready["run_token"] == token,
            "worker_identity_disagreement", role=role)
for rows, role in ((inputs, "sender"), (requests, "controller"), (observed, "observer"),
                   (adapter + prearm, "coordinator")):
    require(all(row["pid"] == pids[role] for row in rows), "row_pid_disagreement", role=role)
require(read_json("observer_ready.json")["host_monotonic_ns"] < requests[0]["s_begin_ns"],
        "observer_not_ready_before_initial_request")

# 준비 256슬롯과 본 구간 400슬롯의 literal payload 및 누락 구간을 전수 확인한다.
prepare = [row for row in inputs if row["phase"] == "prepare"]
trial = [row for row in inputs if row["phase"] == "trial"]
require(len(inputs) == 1252 and len(prepare) == 512 and len(trial) == 740, "input_counts_invalid")
require(Counter((decoded[id(row)][0], row["global_slot"]) for row in prepare)
        == Counter((can_id, n) for n in range(256) for can_id in (0x100, 0x101)), "preparation_slots_invalid")
expected_trial = Counter((0x101, n) for n in range(400))
expected_trial.update((0x100, n) for n in range(400) if not 100 <= n < 160)
require(Counter((decoded[id(row)][0], row["slot"]) for row in trial) == expected_trial,
        "trial_distance_or_background_slots_invalid")
require(len(omissions) == 60 and {row["slot"] for row in omissions} == set(range(100, 160)),
        "omission_diagnostics_invalid")
prepare_origin = prepare[0]["scheduled_ns"]
for row in inputs:
    can_id, payload = decoded[id(row)]
    counter = row["global_slot"] % 256
    expected = ((b"\xe8\x03" + bytes((counter, 1))) if can_id == 0x100
                else bytes((counter, 0, 0, 0))) + token.to_bytes(4, "little")
    require(payload == expected, "input_literal_payload_invalid", global_slot=row["global_slot"])
    require(row["scheduled_ns"] <= row["s_begin_ns"] < row["scheduled_ns"] + PERIOD
            and row["s_begin_ns"] <= row["s_done_ns"] and row["bytes_sent"] == 16,
            "input_send_interval_invalid", global_slot=row["global_slot"])
    if row["phase"] == "trial":
        require(row["global_slot"] == 256 + row["slot"]
                and row["scheduled_ns"] == t0 + row["slot"] * PERIOD, "trial_schedule_invalid")
    else:
        require(row["slot"] is None and row["scheduled_ns"] == prepare_origin + row["global_slot"] * PERIOD,
                "preparation_schedule_invalid")
first_input = next(row for row in trial if decoded[id(row)][0] == 0x100 and row["slot"] == 0)
require(first_input["s_begin_ns"] == t0 and first_input["s_done_ns"] == metadata["t0_done_ns"]
        and metadata["trial_global_slot"] == 256 and end == t0 + 20_000_000_000, "t0_metadata_invalid")

for can_id in (0x100, 0x101, 0x200):
    source = [row for row in (requests if can_id == 0x200 else inputs) if decoded[id(row)][0] == can_id]
    seen = [row for row in observed if decoded[id(row)][0] == can_id]
    compare(source, seen, "independent_" + hex(can_id))
require(len(requests) == 595 and len(observed) == 1847, "request_or_observer_count_invalid")
require(all(left["host_monotonic_ns"] <= right["host_monotonic_ns"]
            for left, right in zip(observed, observed[1:])), "observer_clock_order_invalid")
observed_inputs = [row for row in observed if decoded[id(row)][0] == 0x100
                   and row["host_monotonic_ns"] < arm]
require(len(observed_inputs) == 5, "normal_input_arm_evidence_invalid")
require(all(decoded[id(row)][1][:4] == b"\xe8\x03" + bytes((n, 1))
            for n, row in enumerate(observed_inputs)), "arm_input_literal_invalid")
require(sum(decoded[id(row)][0] == 0x100 and row["s_done_ns"] <= arm for row in inputs) == 5,
        "five_distance_sends_not_completed_before_arm")

# 초기 억제 요청과 시험 중 RX_TIMEOUT 요청을 원시 바이트로 분리한다.
request_observations = [row for row in observed if decoded[id(row)][0] == 0x200]
first_timeout_index = next(i for i, row in enumerate(request_observations)
                           if decoded[id(row)][1][:2] == b"\x01\x02")
first_timeout = request_observations[first_timeout_index]
last_distance = next(row for row in trial if decoded[id(row)][0] == 0x100 and row["slot"] == 99)
q_obs = first_timeout["host_monotonic_ns"]
require(last_distance["s_begin_ns"] + 200_000_000 <= q_obs <= last_distance["s_done_ns"] + 300_000_000,
        "timeout_observation_outside_fixed_window")
for index, (source, seen) in enumerate(zip(requests, request_observations)):
    payload = decoded[id(seen)][1]
    expected_state = b"\x01\x04" if source["s_begin_ns"] < arm else b"\x00\x00" if index < first_timeout_index else b"\x01\x02"
    require(payload[:2] == expected_state and payload[2] == index % 256 and payload[3] == 0,
            "request_state_reason_or_counter_invalid", index=index)
    require(source["s_begin_ns"] <= source["s_done_ns"] and source["bytes_sent"] == 16,
            "request_send_interval_invalid", index=index)
require(any(t0 <= row["host_monotonic_ns"] < q_obs and decoded[id(row)][1][:2] == b"\x00\x00"
            for row in request_observations), "normal_trial_prefix_missing")
restored_requests = [row for row in request_observations if t0 + 8_000_000_000 <= row["host_monotonic_ns"] <= end]
require(restored_requests and all(decoded[id(row)][1][:2] == b"\x01\x02" for row in restored_requests),
        "request_not_latched_after_restore")
require(any(end - PERIOD <= row["s_begin_ns"] <= end for row in requests), "request_does_not_reach_run_end")

# 초기 큐의 7개와 arm 이후의 588개를 합쳐 실제 요청 전부를 대조한다.
require(len(prearm) == 7 and len(adapter) == len(events) == 588, "adapter_counts_invalid")
compare(requests[:7], prearm, "prearm_queue")
compare(requests[7:], adapter, "adapter_receive")
require(all(row["s_begin_ns"] < active for row in requests[:7])
        and all(row["s_begin_ns"] >= active for row in requests[7:]), "adapter_active_boundary_invalid")
durations, successful_calls = [], []
for index, (source, rx, event) in enumerate(zip(requests[7:], adapter, events), 7):
    payload = decoded[id(rx)][1]
    stop, reason, counter = payload[:3]
    require(event["raw_frame_hex"] == rx["raw_frame_hex"] and event["a_rx_ns"] == rx["host_monotonic_ns"]
            and event["actor_id"] == rx["actor_id"] == actor, "adapter_event_receive_disagreement", index=index)
    require(event["request"] == {"stop": bool(stop), "reason": reason, "counter": counter, "run_token": token},
            "adapter_request_decode_disagreement", index=index)
    latched = index >= first_timeout_index
    require(event["stop_latched"] is latched and event["first_reason"] == (2 if latched else None)
            and event["action"] == ("APPLY_FULL_BRAKE" if latched else "KEEP_EXISTING_CONTROL"),
            "adapter_latch_invalid", index=index)
    if not latched:
        require(not any(key in event for key in ("a_done_ns", "call_begin_ns", "response")),
                "normal_request_unexpected_brake_call", index=index)
        continue
    require(event["a_rx_ns"] <= event["call_begin_ns"] <= event["a_done_ns"]
            and event["call_completed"] is True, "adapter_call_not_successful", index=index)
    response = event["response"]
    require(response["actor_id"] == actor and response["error"] == "" and response["do_tick_cue"] is False,
            "adapter_call_response_invalid", index=index)
    duration = event["a_done_ns"] - event["a_rx_ns"]
    require(duration <= PERIOD, "adapter_call_exceeds_50ms", index=index, duration_ns=duration)
    durations.append(duration)
    successful_calls.append(event)
first_done = events[first_timeout_index - 7]["a_done_ns"]

# 호출 반환과 이후 tick에서 실제 조회한 제동 및 평면 속도를 연결한다.
for index, row in enumerate(samples):
    velocity = row["velocity_mps"]
    speed = math.hypot(velocity["x"], velocity["y"])
    require(math.isfinite(speed) and math.isclose(speed, row["speed_mps"], abs_tol=1e-9, rel_tol=1e-9),
            "actual_velocity_disagreement", index=index)
    require(row["actor_id"] == actor and row["tick_begin_monotonic_ns"] <= row["tick_done_monotonic_ns"] <= row["host_monotonic_ns"]
            and abs(row["simulation_delta_s"] - 0.05) <= 1e-6, "vehicle_identity_or_clock_invalid", index=index)
    row["audit_speed_mps"] = speed
for left, right in zip(samples, samples[1:]):
    require(right["frame"] == left["frame"] + 1
            and abs(right["simulation_time_s"] - left["simulation_time_s"] - 0.05) <= 1e-6
            and right["host_monotonic_ns"] >= left["host_monotonic_ns"], "vehicle_frame_or_time_discontinuity")
drive = [row for row in samples if row["phase"] == "drive" and row["host_monotonic_ns"] <= t0]
initial = drive[-21:]
require(len(initial) == 21 and all(4.5 <= row["audit_speed_mps"] * 3.6 <= 5.5 for row in initial),
        "initial_speed_hold_invalid")
require(all(drive[-1][key] == metadata["trial_ready"][key] for key in ("frame", "simulation_time_s", "host_monotonic_ns")),
        "trial_ready_not_observed")
start, deadline, done = (metadata[key] for key in ("preparation_started_monotonic_ns", "preparation_deadline_monotonic_ns",
                                                "preparation_completed_monotonic_ns"))
require(deadline == start + 30_000_000_000 and start <= arm <= done <= t0 <= deadline,
        "preparation_30_second_deadline_invalid")
g4 = [row for row in samples if row["phase"] == "g4"]
require(all(row["tick_begin_monotonic_ns"] >= t0 for row in g4), "g4_tick_before_t0")
first_applied = next(row for row in g4 if row["tick_begin_monotonic_ns"] >= first_done)
require(full_brake(first_applied), "first_tick_after_call_not_full_brake")
after = [row for row in g4 if row["frame"] >= first_applied["frame"]]
require(all(full_brake(row) for row in after), "actual_brake_not_latched")
streak, hold = [], None
for row in after:
    if row["frame"] > first_applied["frame"] + 40:
        break
    streak = streak + [row] if row["audit_speed_mps"] <= 0.1 and full_brake(row) else []
    if len(streak) == 11:
        hold = streak
        break
require(hold is not None and after[-1]["frame"] >= first_applied["frame"] + 40,
        "stop_hold_not_complete_within_40_frames")
restored_motion = [row for row in after if row["host_monotonic_ns"] >= t0 + 8_000_000_000]
require(restored_motion and all(full_brake(row) for row in restored_motion)
        and restored_motion[-1]["host_monotonic_ns"] >= end, "restored_brake_or_run_end_evidence_missing")
require(g4[-1]["tick_begin_monotonic_ns"] >= max(row["a_done_ns"] for row in successful_calls),
        "vehicle_evidence_after_last_call_missing")

# 당시 기록한 9개 실행 소스를 보존 사본과 대조한다. 현재 코드는 별도 진단이다.
source_hashes = {}
source_dir = BASE / "source" if (BASE / "source").is_dir() else ROOT / "tools"
for name, recorded in metadata["source_sha256"].items():
    source_path = source_dir / name
    actual = sha256(source_path) if source_path.is_file() else None
    current_path = ROOT / "tools" / name
    current = sha256(current_path) if current_path.is_file() else None
    source_hashes[name] = {"recorded": recorded, "recomputed": actual, "matches": recorded == actual,
                           "validated_source": str(source_path.relative_to(ROOT)),
                           "current_tools_sha256": current,
                           "current_tools_matches_recorded": current == recorded}
    require(recorded == actual, "source_sha256_disagreement", file=name)
require(len(source_hashes) == 9, "nine_source_hashes_missing")
raw_names = ("metadata.json", "input_events.jsonl", "can_observer.jsonl", "sut_events.jsonl",
             "adapter_prearm_rx.jsonl", "adapter_rx.jsonl", "adapter_events.jsonl", "vehicle_states.jsonl")
output = {
    "audit_status": "FAIL" if errors else "PASS",
    "scope": "G4_A_RX_TIMEOUT_SECOND_ATTEMPT_HISTORICAL_OBSERVATION_AUDIT",
    "run_id": metadata["run_id"], "baseline": "v1.0", "variant": "A", "scenario": "T-03",
    "audited_utc": datetime.now(timezone.utc).isoformat(),
    "audit_script_sha256": sha256(Path(__file__).resolve()),
    "real_runs_executed_by_audit": 0, "main_comparison_runs_executed": 0,
    "source_imports": "Python 표준 라이브러리만 사용. SUT와 기존 oracle은 가져오지 않음.",
    "failure_count": len(errors), "failures": errors,
    "counts": {"prepare_input_frames": len(prepare), "trial_input_frames": len(trial),
               "trial_distance_frames": sum(decoded[id(row)][0] == 0x100 for row in trial),
               "trial_heartbeat_frames": sum(decoded[id(row)][0] == 0x101 for row in trial),
               "omitted_distance_slots": len(omissions),
               "controller_requests": len(requests), "independent_observed_frames": len(observed),
               "independent_observed_requests": len(request_observations), "normal_inputs_before_arm": len(observed_inputs),
               "prearm_queue_frames": len(prearm), "adapter_received_requests": len(adapter),
               "adapter_events": len(events), "successful_brake_calls": len(successful_calls),
               "vehicle_samples": len(samples), "restored_stop_requests": len(restored_requests),
               "restored_brake_samples": len(restored_motion)},
    "process_ids": pids,
    "timing": {"last_distance_s_begin_ns": last_distance["s_begin_ns"],
               "last_distance_s_done_ns": last_distance["s_done_ns"], "first_timeout_q_obs_ns": q_obs,
               "from_last_send_begin_ms": (q_obs - last_distance["s_begin_ns"]) / 1e6,
               "from_last_send_done_ms": (q_obs - last_distance["s_done_ns"]) / 1e6,
               "allowed_min_after_begin_ms": 200, "allowed_max_after_done_ms": 300,
               "max_adapter_processing_ms": max(durations) / 1e6,
               "first_timeout_a_done_ns": first_done,
               "max_request_send_gap_ms": max(right["s_begin_ns"] - left["s_begin_ns"]
                                               for left, right in zip(requests, requests[1:])) / 1e6},
    "motion": {"initial_speed_sample_count": len(initial),
               "initial_speed_first_frame": initial[0]["frame"], "initial_speed_last_frame": initial[-1]["frame"],
               "initial_speed_min_kph": min(row["audit_speed_mps"] * 3.6 for row in initial),
               "initial_speed_max_kph": max(row["audit_speed_mps"] * 3.6 for row in initial),
               "first_applied_frame": first_applied["frame"],
               "first_applied_simulation_time_s": first_applied["simulation_time_s"],
               "first_applied_tick_begin_ns": first_applied["tick_begin_monotonic_ns"],
               "stop_hold_first_frame": hold[0]["frame"] if hold else None,
               "stop_hold_last_frame": hold[-1]["frame"] if hold else None,
               "stop_hold_sample_count": len(hold) if hold else 0,
               "stop_hold_observed_span_s": hold[-1]["simulation_time_s"] - hold[0]["simulation_time_s"] if hold else None,
               "stop_hold_completed_after_applied_frames": hold[-1]["frame"] - first_applied["frame"] if hold else None,
               "full_brake_maintained_through_frame": after[-1]["frame"]},
    "source_sha256": source_hashes,
    "source_validation_basis": "preserved_source" if source_dir == BASE / "source" else "current_tools_fallback",
    "evidence_sha256": {name: sha256(BASE / name) for name in raw_names},
}
(BASE / "observation_audit.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"audit_status": output["audit_status"], "failure_count": len(errors),
                  "output": str(BASE / "observation_audit.json")}, ensure_ascii=False))
sys.exit(1 if errors else 0)
