"""CARLA 없는 예비시험의 원시 입력과 독립 요청 관측을 판정한다.

SUT, 입력 생성기와 그 내부 verdict를 가져오지 않는다. 차량 요구사항은
미수행으로 남긴다. A/T-04 미충족도 실제 요구사항 FAIL로 보존한다.
"""

from collections import defaultdict, deque
import sys


PERIOD = 50_000_000


def evaluate_message_trial(meta, inputs, observed, sut):
    errors, missing, output_errors = [], [], []
    complete = meta.get("execution_status") == "COMPLETE"
    variant, scenario, token = (meta.get(key) for key in ("variant", "scenario", "run_token"))
    t0, end, global_start = (meta.get(key) for key in ("t0_ns", "trial_end_ns", "trial_global_slot"))
    arm = meta.get("armed", {}).get("host_monotonic_ns")
    pids = meta.get("worker_pids", {})
    required = {"T-01": ("R-01", "R-05"), "T-02": ("R-02", "R-08"),
                "T-03": ("R-03", "R-08"), "T-04": ("R-04", "R-08")}
    if variant not in ("A", "B") or scenario not in required or type(token) is not int or not 0 <= token <= 0xFFFFFFFF:
        raise ValueError("방식, 시나리오와 uint32 token이 필요합니다")
    requirements = {key: {"status": "INCONCLUSIVE"} for key in required[scenario]}
    requirements.update({key: {"status": "N/A", "reason": "CARLA_NOT_EXECUTED"} for key in ("R-06", "R-07")})

    def need(condition, message):
        if not condition:
            (errors if complete else missing).append(message)

    def raw(row):
        try:
            data = bytes.fromhex(row["raw_frame_hex"])
        except (KeyError, TypeError, ValueError):
            return None
        if len(data) != 16 or data[4:8] != b"\x08\x00\x00\x00":
            return None
        identifier = int.from_bytes(data[:4], sys.byteorder)
        return (identifier, data[8:], data) if identifier in (0x100, 0x101, 0x200) else None

    def stream(rows, event, role):
        result = []
        for row in rows:
            if row.get("event") != event:
                continue
            parsed = raw(row)
            if parsed is None:
                errors.append(role + ": 원시 프레임 형식 오류")
                continue
            identifier, payload, frame = parsed
            if row.get("pid") != pids.get(role):
                errors.append(role + ": PID 불일치")
            expected_fields = {"arbitration_id": identifier, "dlc": 8, "data_hex": payload.hex(),
                               "extended": False, "remote": False, "error_frame": False}
            if any(type(row.get(key)) is not type(value) or row.get(key) != value for key, value in expected_fields.items()):
                errors.append(role + ": 원시 바이트/해석 필드 불일치")
            if int.from_bytes(payload[4:], "little") != token:
                errors.append(role + ": token 불일치")
            result.append((row, identifier, payload, frame))
        return result

    sent = stream(inputs, "tx", "sender")
    obs = stream(observed, "rx", "observer")
    requests = stream(sut, "request_tx", "controller")
    need(len(pids) == 3 and all(type(value) is int and value > 0 for value in pids.values())
         and len(set(pids.values())) == 3 and meta.get("coordinator_pid") not in pids.values(), "독립 worker 식별 부족")
    for role in ("sender", "observer", "controller"):
        record = meta.get("worker_results", {}).get(role, {})
        need(type(meta.get(role + "_exit_code")) is int and meta[role + "_exit_code"] == 0
             and record.get("status") == "COMPLETE" and record.get("role") == role and record.get("pid") == pids.get(role)
             and record.get("run_token") == token and record.get("exit_code") == 0, role + ": 종료 근거 부족")
    have_times = all(type(value) is int and value >= 0 for value in (t0, end, arm, global_start))
    need(have_times, "arm/T0/종료/전역 슬롯 근거 부족")
    if have_times:
        if end != t0 + 20_000_000_000 or not arm < t0 or global_start <= 0 or global_start % 256:
            errors.append("시작 순번 또는 20초 구간 불일치")
        start, deadline = meta.get("preparation_started_monotonic_ns"), meta.get("preparation_deadline_monotonic_ns")
        need(type(start) is int and type(deadline) is int and deadline == start + 30_000_000_000
             and start <= arm < t0 <= deadline, "30초 준비 기한 근거 부족")
        for role in ("sender", "controller", "observer"):
            done = meta.get("worker_results", {}).get(role, {}).get("done_monotonic_ns")
            need(type(done) is int and done >= end, role + ": 20초 종료 근거 부족")

    # 각 원시 관측을 FIFO로 대응해 순번 회전과 반복 payload도 누락 없이 확인한다.
    queues = defaultdict(deque)
    previous_rx = None
    for row, identifier, payload, frame in obs:
        stamp = row.get("host_monotonic_ns")
        if type(stamp) is not int or stamp < 0 or (previous_rx is not None and stamp < previous_rx):
            errors.append("독립 관측 시각 오류")
            continue
        previous_rx = stamp
        queues[frame].append(row)
    pairs = []
    for item in sorted(sent + requests, key=lambda item: item[0].get("s_begin_ns", -1)):
        row, identifier, payload, frame = item
        begin, done = row.get("s_begin_ns"), row.get("s_done_ns")
        if type(begin) is not int or type(done) is not int or not 0 <= begin <= done or row.get("bytes_sent") != 16:
            errors.append("송신 호출/완료 근거 오류")
            continue
        queue = queues[frame]
        if not queue:
            need(False, "독립 관측 누락")
            continue
        receive = queue.popleft()
        if receive["host_monotonic_ns"] < begin:
            errors.append("독립 관측이 송신 시작보다 빠름")
        pairs.append((item, receive))
    need(not any(queues.values()), "대응하지 않는 독립 관측")

    trial, preparation = {}, []
    prepare_origin, previous_global = None, {}
    previous_send = None
    for row, identifier, payload, frame in sent:
        slot, global_slot = row.get("slot"), row.get("global_slot")
        if identifier not in (0x100, 0x101) or type(global_slot) is not int or global_slot < 0:
            errors.append("입력 ID/전역 슬롯 오류")
            continue
        counter, distance = global_slot % 256, 1000
        is_trial = row.get("phase") == "trial"
        if is_trial:
            if type(slot) is not int or not 0 <= slot < 400:
                errors.append("본 구간 슬롯 오류")
                continue
            if scenario == "T-02" and slot >= 100:
                distance = max(50, 1000 - 5 * (slot - 100))
            if identifier == 0x100 and scenario == "T-04" and 100 <= slot < 160:
                counter = 99
            if (identifier, slot) in trial:
                errors.append("본 구간 입력 중복")
            trial[identifier, slot] = row
            if have_times and (global_slot != global_start + slot or row.get("scheduled_ns") != t0 + slot * PERIOD):
                errors.append("본 구간 일정/순번 오류")
        else:
            preparation.append((global_slot, identifier, row))
            if row.get("phase") != "prepare" or slot is not None:
                errors.append("준비 구간 표기 오류")
            if type(row.get("scheduled_ns")) is int:
                origin = row["scheduled_ns"] - global_slot * PERIOD
                if prepare_origin is not None and origin != prepare_origin:
                    errors.append("준비 구간 고정 일정 오류")
                prepare_origin = origin
        if identifier in previous_global and global_slot <= previous_global[identifier]:
            errors.append("입력 전역 슬롯 순서 오류")
        previous_global[identifier] = global_slot
        expected = ((distance.to_bytes(2, "little") + bytes((counter, 1))) if identifier == 0x100
                    else bytes((global_slot % 256, 0, 0, 0))) + token.to_bytes(4, "little")
        if payload != expected:
            errors.append("고정 입력 바이트 불일치")
        scheduled, begin = row.get("scheduled_ns"), row.get("s_begin_ns")
        if type(scheduled) is not int or type(begin) is not int or not scheduled <= begin < scheduled + PERIOD:
            errors.append("입력 슬롯 기한 위반")
        if previous_send is not None and type(begin) is int and begin < previous_send:
            errors.append("입력 송신 순서 오류")
        previous_send = begin
    if have_times:
        expected_slots = {(identifier, n) for n in range(400) for identifier in (0x100, 0x101)
                          if not (scenario == "T-03" and identifier == 0x100 and 100 <= n < 160)}
        need(set(trial) == expected_slots and len(trial) == len(expected_slots), "400슬롯 고정 입력 부족")
        need(len(preparation) == 2 * global_start and {(n, i) for n, i, _ in preparation}
             == {(n, i) for n in range(global_start) for i in (0x100, 0x101)}, "준비 입력 연속성 부족")
        need(sum(i == 0x100 and row["s_done_ns"] <= arm for _, i, row in preparation) >= 5, "arm 전 정상 입력 5개 부족")
        first = trial.get((0x100, 0))
        need(first is not None and first.get("s_begin_ns") == t0, "T0 실제 송신 경계 불일치")

    observed_requests = [(item, receive) for item, receive in pairs if item[1] == 0x200]
    for n, (row, identifier, payload, frame) in enumerate(requests):
        if identifier != 0x200 or payload[2] != n % 256 or payload[3] != 0:
            output_errors.append("요청 ID/순번/예약 byte 오류")
        if not ((payload[0] == 0 and payload[1] == 0) or (payload[0] == 1 and 1 <= payload[1] <= 4)):
            output_errors.append("요청 stop/reason 오류")
        if have_times and row.get("s_begin_ns", arm) < arm and payload[:2] != b"\x01\x04":
            output_errors.append("기동 억제 요청 오류")
    active = [(item, rx) for item, rx in observed_requests
              if have_times and item[0]["s_begin_ns"] >= arm]
    need(bool(requests) and bool(active), "기동/arm 후 요청 관측 부족")
    if have_times:
        need(any(item[0]["s_begin_ns"] < arm and item[2][:2] == b"\x01\x04" for item, _ in observed_requests), "INIT 요청 근거 부족")
        need(any(item[0]["s_begin_ns"] < t0 and item[2][:2] == b"\x00\x00" for item, _ in active), "arm 이후 정상 요청 근거 부족")
        need(bool(active) and active[-1][0][0]["s_begin_ns"] >= end - PERIOD, "run 끝까지 요청 관측 부족")
    stops = [(item, rx) for item, rx in active if item[2][0] == 1 and item[0]["s_begin_ns"] <= end]
    first_stop = stops[0] if stops else None
    expected_reason = 1 if scenario == "T-02" else 3 if scenario == "T-04" else 2
    primary = required[scenario][0]
    metrics = {"input_frames": len(sent), "request_frames": len(requests), "observed_frames": len(obs),
               "trial_input_frames": len(trial), "first_stop_observed_ns": first_stop[1]["host_monotonic_ns"] if first_stop else None}
    if scenario == "T-01":
        if first_stop:
            requirements[primary] = {"status": "FAIL", "reason": "UNNECESSARY_STOP"}
        elif complete:
            requirements[primary] = {"status": "PASS"}
        requirements["R-05"] = dict(requirements[primary])
    else:
        reference = trial.get((0x100, 260 if scenario == "T-02" else 99))
        if reference and first_stop:
            observed_ns = first_stop[1]["host_monotonic_ns"]
            lower = reference["s_begin_ns"] + (0 if scenario == "T-02" else 200_000_000)
            upper = reference["s_done_ns"] + (100_000_000 if scenario == "T-02" else 300_000_000)
            ok = lower <= observed_ns <= upper and first_stop[0][2][1] == expected_reason
            requirements[primary] = {"status": "PASS" if ok else "FAIL", "reason": "WITHIN_WINDOW" if ok else "EARLY_LATE_OR_WRONG_REASON"}
            metrics["request_after_reference_send_done_ms"] = (observed_ns - reference["s_done_ns"]) / 1e6
        elif complete:
            requirements[primary] = {"status": "FAIL", "reason": "STOP_NOT_OBSERVED"}
        if first_stop:
            first_source = first_stop[0][0]["s_begin_ns"]
            tail = [(item, rx) for item, rx in active if item[0]["s_begin_ns"] >= first_source]
            maintained = all(item[2][:2] == bytes((1, first_stop[0][2][1])) for item, _ in tail)
            if not maintained:
                requirements["R-08"] = {"status": "FAIL", "reason": "STOP_RELEASED"}
            elif complete:
                requirements["R-08"] = {"status": "PASS" if tail[-1][0][0]["s_begin_ns"] >= end - PERIOD else "INCONCLUSIVE"}
        elif complete:
            requirements["R-08"] = {"status": "N/A", "reason": "NO_STOP_TO_LATCH"}
    if errors:
        for key in required[scenario]:
            if requirements[key]["status"] == "PASS":
                requirements[key] = {"status": "INCONCLUSIVE", "reason": "EVIDENCE_OR_INPUT_ERROR"}
    evidence_valid = (complete and not errors and not missing
                      and all(requirements[key]["status"] != "INCONCLUSIVE" for key in required[scenario]))
    requirements["R-09"] = {"status": "N/A", "reason": "MESSAGE_EVIDENCE_ONLY",
                            "message_evidence_valid": evidence_valid}
    return {"scope": "MESSAGE_LEVEL_PRELIMINARY_ONLY", "carla_executed": False,
            "evidence_valid": evidence_valid,
            "evidence_errors": errors, "missing_evidence": missing, "sut_output_errors": output_errors,
            "requirements": requirements, "metrics": metrics, "main_trials_executed": 0}
