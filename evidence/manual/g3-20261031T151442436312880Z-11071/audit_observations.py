"""이 실행의 원시 자료를 별도 계산한다. SUT와 기존 판정기를 가져오지 않는다.

실행 폴더를 인자로 받으며 결과는 표준 출력에만 쓴다. 과거 증거를 덮어쓰지 않는다.
"""

import hashlib
import json
import math
from pathlib import Path
import sys


run = Path(sys.argv[1])
metadata = json.loads((run / "metadata.json").read_text())
result = json.loads((run / "result.json").read_text())


def rows(name):
    return [json.loads(line) for line in (run / name).read_text().splitlines() if line]


def require(condition, message):
    if not condition:
        raise ValueError(message)


tx, observer, rx, events, samples = [rows(name) for name in (
    "input_events.jsonl", "can_observer.jsonl", "adapter_rx.jsonl",
    "adapter_events.jsonl", "vehicle_states.jsonl")]
require(all(len(stream) == 20 for stream in (tx, observer, rx, events)), "20개 원시 기록 필요")
for slot in range(20):
    stop = 1 if 5 <= slot < 10 else 0
    expected = ((0x200).to_bytes(4, sys.byteorder) + bytes((8, 0, 0, 0))
                + bytes((stop, stop, slot, 0)) + metadata["run_token"].to_bytes(4, "little"))
    require(all(bytes.fromhex(stream[slot]["raw_frame_hex"]) == expected
                for stream in (tx, observer, rx, events)), "원시 프레임 불일치")
    require(tx[slot]["s_begin_ns"] <= min(observer[slot]["host_monotonic_ns"],
                                         rx[slot]["host_monotonic_ns"]), "수신이 송신보다 빠름")
    require(tx[slot]["scheduled_ns"] <= tx[slot]["s_begin_ns"]
            < tx[slot]["scheduled_ns"] + 50_000_000, "명목 송신 슬롯 위반")

pids = [metadata["coordinator_pid"], metadata["worker_pids"]["sender"],
        metadata["worker_pids"]["observer"]]
require(len(set(pids)) == 3, "독립 프로세스 필요")
require(all({row["pid"] for row in stream} == {pid}
            for stream, pid in ((tx, pids[1]), (observer, pids[2]), (rx, pids[0]))), "PID 불일치")
durations = []
for slot, event in enumerate(events):
    require(event["a_rx_ns"] == rx[slot]["host_monotonic_ns"], "수신 시각 불일치")
    require(event["stop_latched"] is (slot >= 5), "정지 잠금 위반")
    if slot < 5:
        require(event["action"] == "KEEP_EXISTING_CONTROL" and "a_done_ns" not in event,
                "정상 입력에서 제어 호출 발생")
        continue
    require(event["first_reason"] == 1 and event["action"] == "APPLY_FULL_BRAKE", "제동 유지 위반")
    response = event["response"]
    require(event["call_completed"] and response["actor_id"] == metadata["actor_id"]
            and response["error"] == "" and response["do_tick_cue"] is False, "제동 응답 오류")
    duration = event["a_done_ns"] - event["a_rx_ns"]
    require(0 <= duration <= 50_000_000, "호스트 처리 시간 위반")
    durations.append(duration)

for previous, current in zip(samples, samples[1:]):
    require(current["frame"] == previous["frame"] + 1, "frame 누락")
    require(abs(current["simulation_time_s"] - previous["simulation_time_s"] - .05) <= 1e-6,
            "시뮬레이션 시간 불연속")
for row in samples:
    velocity = row["velocity_mps"]
    require(math.isclose(row["speed_mps"], math.hypot(velocity["x"], velocity["y"]),
                         rel_tol=1e-9, abs_tol=1e-9), "실제 차속 재계산 불일치")
    require(row["actor_id"] == metadata["actor_id"], "차량 식별 불일치")


def braking(row):
    control = row["applied_control"]
    return (control["brake"] >= .999 and control["throttle"] <= .001
            and abs(control["steer"]) <= .001 and not control["hand_brake"])


drive = [row for row in samples if row["phase"] == "drive"]
stable = drive[-21:]
require(len(stable) == 21 and all(4.5 <= row["speed_mps"] * 3.6 <= 5.5 for row in stable),
        "초기 차속 1초 유지 실패")
after = [row for row in samples if row["phase"] == "g3"
         and row["tick_begin_monotonic_ns"] >= events[5]["a_done_ns"]]
applied = next(row for row in after if braking(row))
after = [row for row in after if row["frame"] >= applied["frame"]]
require(all(braking(row) for row in after), "제동 해제 관측")
require(after[-1]["frame"] == applied["frame"] + 40, "2초 관측 창 미완료")
hold = next((after[index:index + 11] for index in range(len(after) - 10)
             if all(row["speed_mps"] <= .1 for row in after[index:index + 11])), None)
require(hold is not None, "정지 0.5초 유지 미관측")
require(any(row["tick_begin_monotonic_ns"] >= events[-1]["a_done_ns"] for row in after),
        "마지막 정상 복원 요청 이후 차량 관측 필요")
require(metadata["post_cleanup"] == {"synchronous_mode": False, "fixed_delta_seconds": None,
                                    "remaining_relevant_actors": []}, "차량/설정 정리 미완료")
require(metadata["actor_destroyed"] and metadata["weather_restored"]
        and metadata["settings_restored"] and not metadata["cleanup_errors"], "정리 오류")

repository = Path(__file__).resolve().parents[3]
for name, digest in metadata["source_sha256"].items():
    require(hashlib.sha256((repository / "tools" / name).read_bytes()).hexdigest() == digest,
            "실행 소스와 현재 소스 불일치: " + name)
require(result["status"] == "PASS" and not result["checks"]["failures"], "최종 판정 불일치")
print(json.dumps({
    "scope": "G3_RAW_OBSERVATION_RECALCULATION_ONLY", "audit_status": "PASS",
    "run_id": run.name, "raw_stream_counts": [len(stream) for stream in (tx, observer, rx, events)],
    "coordinator_sender_observer_pids": pids, "vehicle_sample_count": len(samples),
    "initial_hold_speed_kmh_min": min(row["speed_mps"] * 3.6 for row in stable),
    "initial_hold_speed_kmh_max": max(row["speed_mps"] * 3.6 for row in stable),
    "brake_callback_count": len(durations), "max_receive_to_call_complete_ms": max(durations) / 1e6,
    "first_applied_frame": applied["frame"], "stop_hold_first_frame": hold[0]["frame"],
    "stop_hold_last_frame": hold[-1]["frame"], "stop_hold_sample_count": len(hold),
    "stop_hold_complete_after_applied_nominal_seconds": (hold[-1]["frame"] - applied["frame"]) * .05,
    "final_frame": after[-1]["frame"], "source_sha256_match": True,
    "main_trials_executed": 0,
}, ensure_ascii=False, indent=2))
