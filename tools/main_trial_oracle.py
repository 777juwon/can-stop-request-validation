"""본시험의 입력/요청, adapter 호출과 실제 차량 상태를 분리 판정한다."""

from collections import defaultdict, deque
import math
import sys

from tools.g4_oracle import _held
from tools.main_plan import canonical, digest, load_config, physics_digest
from tools.message_trial_oracle import evaluate_message_trial


def evaluate_main_trial(meta, inputs, observed, sut, received, events, samples):
    """메시지 수준 실패를 유지하고 차량 근거로 R-06~R-09를 확장한다."""
    message_meta = dict(meta)
    # 차량 관측이 중단돼도 완료된 CAN 기록의 판정은 유지한다.
    if all(meta.get("worker_results", {}).get(role, {}).get("status") == "COMPLETE"
           and meta.get(role + "_exit_code") == 0 for role in ("sender", "observer", "controller")):
        message_meta["execution_status"] = "COMPLETE"
    message = evaluate_message_trial(message_meta, inputs, observed, sut)
    requirements = {key: dict(value) for key, value in message["requirements"].items()}
    errors = list(message["evidence_errors"] + message["missing_evidence"])
    operational, adapter_failures = list(message["sut_output_errors"]), []
    metrics = dict(message["metrics"])
    actor, pid, active, end = (meta.get(key) for key in ("actor_id", "coordinator_pid", "adapter_active_ns", "trial_end_ns"))
    config = meta.get("fixed_config", {})
    if config != load_config() or meta.get("config_sha256") != digest(canonical(config)):
        errors.append("고정 설정/해시 불일치")
    if meta.get("physics_normalized_sha256") != config.get("physics_normalized_sha256") or (
            physics_digest(meta.get("vehicle_physics", "")) != config.get("physics_normalized_sha256")):
        errors.append("차량 물리 설정 근거 불일치")
    if (meta.get("client_version") != "0.9.15" or meta.get("server_version") != "0.9.15"
            or meta.get("map", "").rsplit("/", 1)[-1] != "Town04"
            or meta.get("vehicle_blueprint") != "vehicle.tesla.model3"
            or meta.get("spawn_index") != config.get("spawn_index")
            or meta.get("spawn_transform") != config.get("spawn_transform")
            or meta.get("ackermann_controller_settings") != config.get("ackermann_settings")):
        errors.append("서버/차량/고정 초기 조건 근거 불일치")

    def frame(row):
        try:
            value = bytes.fromhex(row["raw_frame_hex"])
        except (KeyError, TypeError, ValueError):
            return None
        if len(value) != 16 or int.from_bytes(value[:4], sys.byteorder) != 0x200 or value[4:8] != b"\x08\0\0\0":
            return None
        return value

    sources = [row for row in sut if row.get("event") == "request_tx" and type(row.get("s_begin_ns")) is int]
    source_queue = defaultdict(deque)
    event_queue = defaultdict(deque)
    for row in sources:
        source_queue[row.get("raw_frame_hex")].append(row)
    arm = meta.get("armed", {}).get("acknowledged_monotonic_ns", meta.get("armed", {}).get("host_monotonic_ns"))
    if (type(actor) is not int or actor <= 0 or type(pid) is not int or pid <= 0
            or type(active) is not int or type(arm) is not int or not arm <= active < meta.get("t0_ns", 0)):
        errors.append("adapter의 arm/활성화/식별 근거 부족")
    prearm = meta.get("adapter_prearm_rx")
    if not isinstance(prearm, list):
        errors.append("adapter 초기 큐 관측 근거 부족")
        prearm = []
    previous_prearm = None
    for rx in prearm:
        raw, stamp = frame(rx), rx.get("host_monotonic_ns")
        if (raw is None or rx.get("pid") != pid or rx.get("actor_id") != actor
                or type(stamp) is not int or type(active) is not int or stamp > active
                or previous_prearm is not None and stamp < previous_prearm):
            errors.append("adapter 초기 큐 형식/식별/시각 오류")
            continue
        previous_prearm = stamp
        queue = source_queue[rx["raw_frame_hex"]]
        if not queue or stamp < queue[0]["s_begin_ns"]:
            errors.append("adapter 초기 큐와 송신 대응 누락")
        else:
            queue.popleft()
    for row in events:
        if row.get("event") == "request":
            event_queue[row.get("raw_frame_hex")].append(row)
    latched, reason, calls, r6_failures = False, None, [], []
    last_call_done, post_window_errors = None, []
    previous_rx = None
    for rx in received:
        raw = frame(rx)
        stamp = rx.get("host_monotonic_ns")
        if (raw is None or rx.get("pid") != pid or rx.get("actor_id") != actor
                or type(stamp) is not int or type(active) is not int or stamp < active
                or previous_rx is not None and stamp < previous_rx):
            errors.append("adapter 수신 형식/식별/시각 오류")
            continue
        previous_rx = stamp
        if last_call_done is not None and stamp < last_call_done:
            errors.append("단일 adapter의 이전 호출 완료 전 다음 수신 시각")
        sq, eq = source_queue[rx["raw_frame_hex"]], event_queue[rx["raw_frame_hex"]]
        if not sq or not eq:
            errors.append("adapter 수신과 송신/이벤트 대응 누락")
            continue
        source, event = sq.popleft(), eq.popleft()
        if stamp < source["s_begin_ns"] or event.get("a_rx_ns") != stamp or event.get("actor_id") != actor:
            errors.append("adapter 원시 수신 경계 불일치")
        stop, raw_reason, counter, reserved = raw[8:12]
        token = int.from_bytes(raw[12:], "little")
        if token != meta.get("run_token") or reserved != 0 or not ((stop == 0 and raw_reason == 0) or (stop == 1 and 1 <= raw_reason <= 4)):
            errors.append("adapter 지원 요청 바이트 불일치")
        if event.get("request") != {"stop": bool(stop), "reason": raw_reason, "counter": counter, "run_token": token}:
            errors.append("adapter 해석과 원시 바이트 불일치")
        if stop and not latched:
            latched, reason = True, raw_reason
        if event.get("stop_latched") is not latched or event.get("first_reason") != reason:
            adapter_failures.append("정지 잠금/최초 원인 불일치")
        if not latched:
            if event.get("action") != "KEEP_EXISTING_CONTROL" or any(key in event for key in ("a_done_ns", "response")):
                adapter_failures.append("정상 요청에서 의도하지 않은 제어")
            continue
        relevant = type(end) is int and source["s_begin_ns"] <= end
        begin, done, response = (event.get(key) for key in ("call_begin_ns", "a_done_ns", "response"))
        if (event.get("action") != "APPLY_FULL_BRAKE" or event.get("call_completed") is not True
                or type(begin) is not int or type(done) is not int or not stamp <= begin <= done
                or not isinstance(response, dict) or response.get("actor_id") != actor
                or response.get("error") != "" or response.get("do_tick_cue") is not False):
            target = errors if event.get("interrupted") else r6_failures if relevant else post_window_errors
            target.append("제동 호출 완료/응답 근거 오류")
            continue
        last_call_done = done
        if relevant:
            calls.append({"source_ns": source["s_begin_ns"], "a_rx_ns": stamp, "a_done_ns": done, "reason": reason})
            if done - stamp > 50_000_000:
                r6_failures.append("수신부터 호출 완료까지 50ms 초과")
    if any(source_queue.values()) or any(event_queue.values()):
        errors.append("adapter 수신/이벤트 전체 관측 누락")
    metrics["adapter_calls"] = len(calls)
    metrics["post_window_call_errors"] = post_window_errors
    metrics["max_processing_ms"] = max((row["a_done_ns"] - row["a_rx_ns"] for row in calls), default=0) / 1e6 if calls else None

    def numeric(value):
        return type(value) in (int, float) and math.isfinite(value)

    valid = []
    for row in samples:
        velocity, control = row.get("velocity_mps", {}), row.get("applied_control", {})
        times = [row.get(key) for key in ("frame", "host_monotonic_ns", "tick_begin_monotonic_ns", "tick_done_monotonic_ns")]
        if (not all(type(t) is int and t >= 0 for t in times)
                or not all(numeric(row.get(key)) for key in ("simulation_time_s", "simulation_delta_s", "speed_mps"))
                or not all(numeric(velocity.get(key)) for key in ("x", "y", "z"))
                or not all(numeric(control.get(key)) for key in ("throttle", "brake", "steer"))
                or type(control.get("hand_brake")) is not bool or row.get("actor_id") != actor):
            errors.append("차량 상태 필드 누락/비정상값")
            continue
        if not times[2] <= times[3] <= times[1] or abs(row["simulation_delta_s"] - .05) > 1e-6:
            errors.append("차량 호스트 시각/고정 간격 불일치")
        speed = math.hypot(velocity["x"], velocity["y"])
        if not math.isclose(speed, row["speed_mps"], rel_tol=1e-9, abs_tol=1e-9):
            errors.append("차량 속도와 원시 velocity 불일치")
        valid.append({**row, "observed_speed_mps": speed})
    for left, right in zip(valid, valid[1:]):
        if (right["frame"] != left["frame"] + 1
                or abs(right["simulation_time_s"] - left["simulation_time_s"] - .05) > 1e-6
                or right["host_monotonic_ns"] < left["host_monotonic_ns"]):
            errors.append("차량 frame/시간 연속성 누락")
    t0 = meta.get("t0_ns")
    trial = [row for row in valid if row.get("phase") == "g4"]
    drive = [row for row in valid if row.get("phase") == "drive" and type(t0) is int and row["host_monotonic_ns"] <= t0]
    stable = _held(drive[-21:], lambda r: 4.5 <= r["observed_speed_mps"] * 3.6 <= 5.5, 21)
    if not stable or not drive or meta.get("trial_ready") != {key: drive[-1][key] for key in ("frame", "simulation_time_s", "host_monotonic_ns")}:
        errors.append("T0 직전 1초 실제 속도 준비 근거 부족")
    metrics["initial_speed_hold"] = stable
    if not trial or type(end) is not int or trial[-1]["host_monotonic_ns"] < end:
        errors.append("20초 종료까지 차량 관측 부족")
    if type(t0) is int and any(row["tick_begin_monotonic_ns"] < t0 for row in trial):
        errors.append("본 구간 차량 관측이 T0보다 이름")

    def braking(row):
        c = row["applied_control"]
        return c["brake"] >= .999 and c["throttle"] <= .001 and abs(c["steer"]) <= .001 and not c["hand_brake"]

    first = calls[0] if calls else None
    prefix = [row for row in trial if type(end) is int and row["tick_begin_monotonic_ns"] <= end
              and (first is None or row["tick_begin_monotonic_ns"] < first["a_done_ns"])]
    if not prefix:
        errors.append("요청 없는 주행의 차량 관측 부족")
    elif any(row["observed_speed_mps"] <= .1 for row in prefix):
        operational.append("요청 없는 주행에서 움직임 부족/임의 정지")
    origin, lane_width = config.get("spawn_transform", {}), meta.get("corridor", {}).get("lane_width_m")
    if not numeric(lane_width) or lane_width <= 0:
        errors.append("도로 폭 관측 근거 부족")
    else:
        yaw = math.radians(origin.get("yaw", 0))
        for row in trial:
            point = row.get("transform", {})
            if not all(numeric(point.get(key)) for key in ("x", "y", "z")):
                errors.append("실제 차량 위치 근거 부족")
                continue
            dx, dy = point["x"] - origin["x"], point["y"] - origin["y"]
            along, lateral = dx * math.cos(yaw) + dy * math.sin(yaw), -dx * math.sin(yaw) + dy * math.cos(yaw)
            if not 0 <= along <= config["corridor_distance_m"] or abs(lateral) > lane_width / 2:
                operational.append("고정 직선 도로 구간 이탈")
                break
    requirements["R-06"] = ({"status": "FAIL", "reason": "; ".join(r6_failures)} if r6_failures else
                             {"status": "PASS"} if calls else {"status": "N/A", "reason": "NO_IN_WINDOW_STOP_REQUEST"})
    metrics.update(first_brake_applied=None, stop_hold=None)
    if first:
        after_call = [row for row in trial if row["tick_begin_monotonic_ns"] >= first["a_done_ns"]]
        applied = after_call[0] if after_call else None
        stopped = _held([row for row in after_call if row["frame"] <= applied["frame"] + 40],
                        lambda r: braking(r) and r["observed_speed_mps"] <= .1, 11) if applied else None
        window_complete = bool(after_call) and after_call[-1]["frame"] >= applied["frame"] + 40
        if applied:
            metrics["first_brake_applied"] = {key: applied[key] for key in ("frame", "simulation_time_s")}
        metrics["stop_hold"] = stopped
        if applied and not braking(applied):
            requirements["R-07"] = {"status": "FAIL", "reason": "NEXT_TICK_NOT_BRAKING"}
        elif stopped:
            requirements["R-07"] = {"status": "PASS"}
        else:
            requirements["R-07"] = {"status": "FAIL" if window_complete else "INCONCLUSIVE", "reason": "STOP_HOLD_NOT_OBSERVED"}
        if not window_complete:
            errors.append("제동 적용 뒤40frame 관측 부족")
        if "R-08" in requirements:
            if adapter_failures or any(not braking(row) for row in after_call):
                requirements["R-08"] = {"status": "FAIL", "reason": "REQUEST_OR_BRAKE_LATCH_RELEASED"}
            elif requirements["R-08"]["status"] == "PASS" and not after_call:
                requirements["R-08"] = {"status": "INCONCLUSIVE"}
    elif message["metrics"]["first_stop_observed_ns"] is not None:
        requirements["R-06"] = {"status": "FAIL" if r6_failures else "INCONCLUSIVE", "reason": "NO_SUCCESSFUL_CONTROL_CALL"}
        requirements["R-07"] = {"status": "INCONCLUSIVE", "reason": "NO_APPLIED_START_FRAME"}
    else:
        requirements["R-07"] = {"status": "N/A", "reason": "NO_IN_WINDOW_STOP_REQUEST"}
    if calls and not any(row["tick_begin_monotonic_ns"] >= calls[-1]["a_done_ns"] for row in trial):
        errors.append("마지막 제동 호출 뒤 차량 표본 부족")
    evidence_valid = message["evidence_valid"] and not errors
    requirements["R-09"] = {"status": "PASS" if evidence_valid else "INCONCLUSIVE", "reason": "FULL_CHAIN_EVIDENCE" if evidence_valid else "EVIDENCE_INCOMPLETE"}
    failures = [{"requirement": key, **value} for key, value in requirements.items() if value["status"] == "FAIL"]
    failures += [{"domain": "operation", "reason": value} for value in operational + adapter_failures]
    return {"scope": "CARLA_FULL_CHAIN_REQUIREMENTS", "requirements": requirements, "metrics": metrics,
            "message_checks": message, "evidence_valid": evidence_valid, "evidence_errors": errors,
            "operational_failures": operational + adapter_failures, "failures": failures,
            "all_checks_passed": evidence_valid and not failures}
