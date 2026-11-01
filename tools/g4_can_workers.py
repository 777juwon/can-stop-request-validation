#!/usr/bin/env python3
"""G4 첫 A/T-03 연결을 위한 독립 거리 송신기, 관측기와 제어기다.

이 파일은 CARLA를 호출하지 않으며 본시험 실행기가 아니다. 준비 입력부터
계속되는 순번, 명시적 arm과 시험 시작 신호를 전용 증거 폴더에 보존한다.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time
import traceback


# 격리 실행에서도 저장소 안의 도구만 명시적으로 불러온다.
REPOSITORY = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY))
from tools.g3_integration_can import StopSignals  # noqa: E402
from tools.g3_request_smoke import (  # noqa: E402
    CAN_FRAME, InputFailure, emit, encode_request, frame_fields, inspect_link, open_bus, write_json,
)


SCOPE = "CAN_TRIAL_WORKERS_V1_ONLY"
PERIOD_NS = 50_000_000
POLL_NS = 10_000_000
PREPARE_NS = 30_000_000_000
WATCHDOG_NS = 65_000_000_000
TRIAL_SLOTS = 400
DISTANCE_ID = 0x100
HEARTBEAT_ID = 0x101
REQUEST_ID = 0x200
EXIT_CODES = {"COMPLETE": 0, "ENV_ERROR": 2, "TOOL_ERROR": 3,
              "INPUT_ERROR": 4, "SUT_ERROR": 5, "INTERRUPTED": 130}


class SutFailure(Exception):
    """코어 내부 오류를 실제 소켓 또는 파일 입출력 실패와 구분한다."""


def call_core(operation, *args):
    """코어 호출에서 나온 예외의 출처를 보존한다."""
    try:
        return operation(*args)
    except Exception as exc:
        name = getattr(operation, "__name__", type(operation).__name__)
        raise SutFailure(f"{name}: {exc}") from exc


def atomic_write_json(path: Path, value) -> None:
    """완성한 JSON만 공개하고 기존 파일이나 심볼릭 링크를 덮어쓰지 않는다.

    실시간 신호 교환은 close 뒤 hard link로 완성본을 공개한다. 이 경로에
    동기 디스크 쓰기를 넣어 송신/검사 주기를 막지 않는다. 전원 손실 뒤의
    디스크 복구 보장과 실행 중 파일 공개의 원자성은 별개다.
    """
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink()


def fixture_frames(token: int, global_slot: int, trial_slot: int | None = None,
                   scenario: str = "T-03") -> list[bytes]:
    """기준선의 네 수치 입력과 배경 심박을 구성한다. 준비 입력은 원거리다."""
    if scenario not in ("T-01", "T-02", "T-03", "T-04"):
        raise ValueError("정의된 T-01~T-04 시나리오가 필요합니다")
    for name, value, maximum in (("run_token", token, 0xFFFFFFFF),
                                 ("global_slot", global_slot, None),
                                 ("trial_slot", trial_slot, TRIAL_SLOTS - 1)):
        if value is None and name == "trial_slot":
            continue
        if type(value) is not int or value < 0 or (maximum is not None and value > maximum):
            raise ValueError(f"{name}: 허용 범위의 정수가 필요합니다")
    counter = global_slot % 256
    if trial_slot is not None and counter != trial_slot % 256:
        raise ValueError("준비 순번과 시험 순번이 이어지지 않습니다")
    distance_cm = (max(50, 1000 - 5 * (trial_slot - 100))
                   if scenario == "T-02" and trial_slot is not None and trial_slot >= 100 else 1000)
    distance_counter = 99 if scenario == "T-04" and trial_slot is not None and 100 <= trial_slot < 160 else counter
    distance = struct.pack("<HBBI", distance_cm, distance_counter, 1, token)
    heartbeat = bytes([counter, 0, 0, 0]) + token.to_bytes(4, "little")
    frames = []
    if not (scenario == "T-03" and trial_slot is not None and 100 <= trial_slot < 160):
        frames.append(CAN_FRAME.pack(DISTANCE_ID, 8, distance))
    frames.append(CAN_FRAME.pack(HEARTBEAT_ID, 8, heartbeat))
    return frames


def trial_start_slot(next_global_slot: int) -> int:
    """아직 보내지 않은 슬롯부터 양의 순번 0 경계를 찾는다."""
    if type(next_global_slot) is not int or next_global_slot < 0:
        raise ValueError("다음 전역 슬롯은 음수가 아닌 정수여야 합니다")
    return max(256, ((next_global_slot + 255) // 256) * 256)


def read_command(path: Path, token: int, earliest_ns: int, now_ns: int) -> dict | None:
    """이번 준비 이후에 만들어진 동일 token의 명시적 명령만 인정한다."""
    if not os.path.lexists(path):
        return None
    if path.is_symlink() or not path.is_file():
        raise InputFailure(f"명령은 일반 JSON 파일이어야 합니다: {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        # 부모가 파일 확인 사이에 명령을 만들 수 있어 읽기 완료 시각도 확인한다.
        observed_ns = max(now_ns, time.monotonic_ns())
        stamp = value["host_monotonic_ns"]
        if type(value["run_token"]) is not int or value["run_token"] != token:
            raise ValueError("run_token 불일치")
        if type(stamp) is not int or not earliest_ns <= stamp <= observed_ns:
            raise ValueError("오래되었거나 미래인 명령 시각")
    except (ValueError, TypeError, KeyError) as exc:
        raise InputFailure(f"잘못된 {path.name}: {exc}") from exc
    return value


def write_ready(output: Path, role: str, interface: str, token: int, ready_ns: int) -> None:
    """socket과 로그 준비가 끝난 역할의 식별 정보를 원자적으로 공개한다."""
    atomic_write_json(output / f"{role}_ready.json", {
        "scope": SCOPE, "role": role, "pid": os.getpid(), "run_token": token,
        "interface": interface, "host_monotonic_ns": ready_ns,
    })


def sleep_until(due_ns: int, signals: StopSignals, watchdog_ns: int) -> None:
    """송신 취소와 유한 watchdog을 확인하며 예정 시각까지 기다린다."""
    while True:
        signals.check_sender()
        now = time.monotonic_ns()
        if now >= watchdog_ns:
            raise OSError("송신기 65초 watchdog 초과")
        if now >= due_ns:
            return
        time.sleep(min((due_ns - now) / 1e9, POLL_NS / 1e9))


def sender(interface: str, output: Path, token: int, signals: StopSignals,
           scenario: str = "T-03") -> dict:
    """준비 순번을 유지한 채 다음 0 경계부터 선택한 기준선 입력을 송신한다."""
    with open_bus(interface) as bus, (output / "input_events.jsonl").open("x", encoding="utf-8") as stream:
        ready = time.monotonic_ns()
        watchdog, prepare_deadline = ready + WATCHDOG_NS, ready + PREPARE_NS
        first_due = ready + PERIOD_NS
        write_ready(output, "sender", interface, token, ready)
        global_slot = 0
        trial_global = trial_origin = trial_done = requested_ns = None
        counts = {"prepare_distance_frames": 0, "prepare_heartbeat_frames": 0,
                  "trial_distance_frames": 0, "trial_heartbeat_frames": 0}
        while True:
            slot = global_slot - trial_global if trial_global is not None and global_slot >= trial_global else None
            if slot == TRIAL_SLOTS:
                sleep_until(trial_origin + TRIAL_SLOTS * PERIOD_NS, signals, watchdog)
                return {**counts, "sent_frames": sum(counts.values()),
                        "ready_monotonic_ns": ready, "watchdog_deadline_ns": watchdog,
                        "trial_requested_monotonic_ns": requested_ns, "t0_ns": trial_origin,
                        "t0_done_ns": trial_done, "trial_global_slot": trial_global,
                        "trial_first_scheduled_ns": trial_origin,
                        "trial_end_ns": trial_origin + TRIAL_SLOTS * PERIOD_NS}
            due = first_due + global_slot * PERIOD_NS if trial_origin is None else trial_origin + slot * PERIOD_NS
            sleep_until(due, signals, watchdog)
            now = time.monotonic_ns()
            if trial_origin is None and now >= prepare_deadline:
                raise OSError("송신 준비와 시험 시작을 30초 안에 마치지 못했습니다")
            if trial_global is None:
                command = read_command(output / "trial_requested.json", token, ready, now)
                if command is not None:
                    requested_ns = command["host_monotonic_ns"]
                    trial_global = trial_start_slot(global_slot)
            slot = global_slot - trial_global if trial_global is not None and global_slot >= trial_global else None
            phase = "trial" if slot is not None else "prepare"
            if now >= due + PERIOD_NS:
                emit(stream, event="missed_slot", phase=phase, slot=slot, global_slot=global_slot,
                     scheduled_ns=due, host_monotonic_ns=now, pid=os.getpid())
                raise InputFailure(f"전역 송신 슬롯 {global_slot}를 놓쳐 밀린 입력을 전송하지 않습니다")
            if scenario == "T-03" and slot is not None and 100 <= slot < 160:
                emit(stream, event="distance_omitted", phase=phase, slot=slot, global_slot=global_slot,
                     scheduled_ns=due, host_monotonic_ns=now, pid=os.getpid(), arbitration_id=DISTANCE_ID)
            for raw in fixture_frames(token, global_slot, slot, scenario):
                begin = time.monotonic_ns()
                if begin >= due + PERIOD_NS:
                    emit(stream, event="missed_slot", phase=phase, slot=slot, global_slot=global_slot,
                         scheduled_ns=due, host_monotonic_ns=begin, pid=os.getpid())
                    raise InputFailure(f"전역 송신 슬롯 {global_slot}의 프레임 송신이 지연됐습니다")
                original_due = due
                if slot == 0 and trial_origin is None:
                    trial_origin = due = begin
                sent = bus.send(raw)
                done = time.monotonic_ns()
                fields = frame_fields(raw)
                emit(stream, event="tx", phase=phase, slot=slot, global_slot=global_slot,
                     scheduled_ns=due, planned_due_ns=original_due, s_begin_ns=begin, s_done_ns=done,
                     bytes_sent=sent, pid=os.getpid(), **fields)
                if sent != CAN_FRAME.size:
                    raise InputFailure("Classic CAN 프레임 일부만 송신됐습니다")
                kind = "distance" if fields["arbitration_id"] == DISTANCE_ID else "heartbeat"
                counts[f"{phase}_{kind}_frames"] += 1
                if slot == 0 and kind == "distance":
                    trial_done = done
            if slot == 0:
                # 같은 슬롯의 거리/심박을 모두 보낸 뒤 시작 정보를 공개한다.
                publish_begin = time.monotonic_ns()
                atomic_write_json(output / "trial_started.json", {
                    "scope": SCOPE, "pid": os.getpid(), "run_token": token,
                    "host_monotonic_ns": trial_done, "t0_ns": trial_origin, "t0_done_ns": trial_done,
                    "trial_global_slot": global_slot, "trial_first_scheduled_ns": trial_origin,
                    "trial_end_ns": trial_origin + TRIAL_SLOTS * PERIOD_NS,
                })
                emit(stream, event="trial_start_published", host_monotonic_ns=time.monotonic_ns(),
                     publish_begin_ns=publish_begin, t0_ns=trial_origin, pid=os.getpid())
            global_slot += 1


def observer(interface: str, output: Path, token: int, signals: StopSignals) -> dict:
    """세 ID의 외래 token과 잘못된 프레임도 원시 수신 증거로 남긴다."""
    count = errors = 0
    with open_bus(interface) as bus, (output / "can_observer.jsonl").open("x", encoding="utf-8") as stream:
        bus.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FILTER,
                       b"".join(struct.pack("=II", item, 0x7FF)
                                for item in (DISTANCE_ID, HEARTBEAT_ID, REQUEST_ID)))
        ready = time.monotonic_ns()
        watchdog = ready + WATCHDOG_NS
        write_ready(output, "observer", interface, token, ready)
        draining = False
        received_before_termination = 0
        while True:
            if signals.interrupt_requested:
                raise KeyboardInterrupt("관측기 사용자 취소")
            if time.monotonic_ns() >= watchdog:
                raise OSError("관측기 65초 watchdog 초과")
            if signals.terminate_requested and not draining:
                # 송신기와 제어기가 끝난 뒤 남은 수신 큐까지 보존한다.
                bus.settimeout(0.0)
                draining = True
                received_before_termination = count
            try:
                raw = bus.recv(72)
            except (socket.timeout, BlockingIOError):
                if draining:
                    return {"received_frames": count, "decode_errors": errors,
                            "ready_monotonic_ns": ready, "watchdog_deadline_ns": watchdog,
                            "termination": "COORDINATOR_SIGTERM",
                            "drained_after_sigterm_frames": count - received_before_termination,
                            "drain_completed_monotonic_ns": time.monotonic_ns()}
                continue
            stamp = time.monotonic_ns()
            event = {"event": "rx", "pid": os.getpid(), "host_monotonic_ns": stamp,
                     "raw_frame_hex": raw.hex()}
            try:
                event.update(frame_fields(raw))
            except ValueError as exc:
                event["decode_error"] = str(exc)
                errors += 1
            emit(stream, **event)
            count += 1


def controller(interface: str, output: Path, token: int, signals: StopSignals,
               variant: str = "A") -> dict:
    """10 ms 감시와 명시적 arm을 수행하며 전이 즉시 요청을 보낸다."""
    from tools.g4_controller_core import DistanceTimeoutController, G4ArmError
    from tools.sequence_controller_core import SequenceProgressController

    if variant not in ("A", "B"):
        raise ValueError("A 또는 B 방식이 필요합니다")

    with open_bus(interface) as bus, (output / "sut_events.jsonl").open("x", encoding="utf-8") as stream:
        bus.settimeout(POLL_NS / 1e9)
        bus.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FILTER,
                       b"".join(struct.pack("=II", item, 0x7FF) for item in (DISTANCE_ID, HEARTBEAT_ID)))
        ready = time.monotonic_ns()
        watchdog, prepare_deadline = ready + WATCHDOG_NS, ready + PREPARE_NS
        core = call_core(DistanceTimeoutController if variant == "A" else SequenceProgressController, token, ready)
        event_index = request_counter = transmitted = 0
        input_ready_ns = armed_ns = acknowledged_ns = None

        def flush_events() -> None:
            nonlocal event_index
            for event in core.events[event_index:]:
                emit(stream, **{**event, "pid": os.getpid()})
            event_index = len(core.events)

        def transmit(scheduled_ns: int | None = None) -> int:
            nonlocal request_counter, transmitted
            raw = CAN_FRAME.pack(REQUEST_ID, 8, encode_request(int(core.stop), core.reason, request_counter, token))
            begin = time.monotonic_ns()
            sent = bus.send(raw)
            done = time.monotonic_ns()
            emit(stream, event="request_tx", pid=os.getpid(), host_monotonic_ns=begin,
                 s_begin_ns=begin, s_done_ns=done, scheduled_ns=scheduled_ns,
                 bytes_sent=sent, state=core.state, **frame_fields(raw))
            if sent != CAN_FRAME.size:
                raise InputFailure("정지 요청 CAN 프레임 일부만 송신됐습니다")
            request_counter = (request_counter + 1) % 256
            transmitted += 1
            return begin + PERIOD_NS

        flush_events()
        next_request = transmit()
        write_ready(output, "controller", interface, token, ready)
        while True:
            if signals.interrupt_requested:
                raise KeyboardInterrupt("제어기 사용자 취소")
            now = time.monotonic_ns()
            if now >= watchdog:
                raise OSError("제어기 65초 watchdog 초과")
            if signals.terminate_requested:
                flush_events()
                return {"request_frames": transmitted, "ready_monotonic_ns": ready,
                        "watchdog_deadline_ns": watchdog, "termination": "COORDINATOR_SIGTERM",
                        "input_ready_monotonic_ns": input_ready_ns, "armed_monotonic_ns": armed_ns,
                        "acknowledged_monotonic_ns": acknowledged_ns,
                        "snapshot": call_core(core.snapshot)}
            if armed_ns is None and now >= prepare_deadline:
                raise OSError("제어기 준비와 명시적 arm을 30초 안에 마치지 못했습니다")
            before = (core.state, core.stop, core.reason)
            call_core(core.poll, now)
            flush_events()
            if before != (core.state, core.stop, core.reason):
                next_request = transmit()
            if input_ready_ns is None and core.valid_normal_count >= 5:
                input_ready_ns = now
                atomic_write_json(output / "controller_input_ready.json", {
                    "scope": SCOPE, "role": "controller", "pid": os.getpid(), "run_token": token,
                    "host_monotonic_ns": now, "snapshot": call_core(core.snapshot),
                })
            if armed_ns is None:
                command = read_command(output / "controller_arm.json", token,
                                       input_ready_ns if input_ready_ns is not None else ready, now)
                if command is not None:
                    if input_ready_ns is None:
                        raise InputFailure("정상 입력 5개 확인 전 arm 명령을 거부합니다")
                    arm_begin_ns = time.monotonic_ns()
                    try:
                        core.arm(arm_begin_ns)
                    except G4ArmError as exc:
                        flush_events()
                        raise InputFailure(f"arm 조건 불충족: {exc}") from exc
                    except Exception as exc:
                        raise SutFailure(f"arm: {exc}") from exc
                    flush_events()
                    if core.stop != 0 or core.reason != 0:
                        raise RuntimeError("arm 후 정상 요청 상태가 아닙니다")
                    next_request = transmit()
                    armed_ns = arm_begin_ns
                    acknowledged_ns = time.monotonic_ns()
                    atomic_write_json(output / "controller_armed.json", {
                        "scope": SCOPE, "role": "controller", "pid": os.getpid(), "run_token": token,
                        "host_monotonic_ns": armed_ns, "acknowledged_monotonic_ns": acknowledged_ns,
                        "arm_command": command, "snapshot": call_core(core.snapshot),
                    })
            now = time.monotonic_ns()
            if now >= next_request:
                next_request = transmit(next_request)
            try:
                raw = bus.recv(72)
            except socket.timeout:
                continue
            received = time.monotonic_ns()
            before = (core.state, core.stop, core.reason)
            call_core(core.on_frame, raw, received)
            flush_events()
            if before != (core.state, core.stop, core.reason):
                next_request = transmit()


def run_worker(args: argparse.Namespace) -> int:
    """역할별 독립 사전검사와 예외 분류를 기존 증거 보존 조건으로 수행한다."""
    output = args.output_dir.resolve()
    if not output.is_dir():
        raise OSError("coordinator가 새 증거 폴더를 먼저 만들어야 합니다")
    owned = [f"{args.worker}_{suffix}" for suffix in
             ("result.json", "ready.json", "preflight.json", "error.txt")]
    owned += {"sender": ["input_events.jsonl", "trial_started.json"],
              "observer": ["can_observer.jsonl"],
              "controller": ["sut_events.jsonl", "controller_input_ready.json", "controller_armed.json"]}[args.worker]
    if any(os.path.lexists(output / name) for name in owned):
        raise FileExistsError("기존 worker 증거가 있어 덮어쓰지 않습니다")
    signals = StopSignals()
    previous = {number: signal.signal(number, signals.handler)
                for number in (signal.SIGTERM, signal.SIGINT)}
    result = {"scope": SCOPE, "role": args.worker, "pid": os.getpid(), "status": "TOOL_ERROR",
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "begin_monotonic_ns": time.monotonic_ns(), "interface": args.interface,
              "run_token": args.run_token, "variant": getattr(args, "variant", "A"),
              "scenario": getattr(args, "scenario", "T-03")}
    try:
        inspect_link(args.interface, output, record_name=f"{args.worker}_preflight.json")
        operation = {"sender": sender, "observer": observer, "controller": controller}[args.worker]
        options = ({"scenario": result["scenario"]} if args.worker == "sender" and result["scenario"] != "T-03"
                   else {"variant": result["variant"]} if args.worker == "controller" and result["variant"] != "A" else {})
        result.update(operation(args.interface, output, args.run_token, signals, **options))
        result["status"] = "COMPLETE"
    except (Exception, KeyboardInterrupt) as exc:
        result.update(status="INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else
                      "INPUT_ERROR" if isinstance(exc, InputFailure) else
                      "ENV_ERROR" if isinstance(exc, (OSError, subprocess.TimeoutExpired)) else
                      "SUT_ERROR" if args.worker == "controller" else "TOOL_ERROR",
                      error=str(exc), error_type=type(exc).__name__)
        with (output / f"{args.worker}_error.txt").open("x", encoding="utf-8") as error_file:
            error_file.write(traceback.format_exc())
    finally:
        result.update(finished_utc=datetime.now(timezone.utc).isoformat(), done_monotonic_ns=time.monotonic_ns(),
                      terminate_requested=signals.terminate_requested,
                      interrupt_requested=signals.interrupt_requested, signal_number=signals.signal_number)
        result["exit_code"] = EXIT_CODES[result["status"]]
        try:
            atomic_write_json(output / f"{args.worker}_result.json", result)
        finally:
            for number, old_handler in previous.items():
                signal.signal(number, old_handler)
    return result["exit_code"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=("sender", "observer", "controller"), required=True)
    parser.add_argument("--interface", default="vcan0")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-token", type=int, required=True)
    parser.add_argument("--variant", choices=("A", "B"), default="A")
    parser.add_argument("--scenario", choices=("T-01", "T-02", "T-03", "T-04"), default="T-03")
    args = parser.parse_args()
    if not 0 <= args.run_token <= 0xFFFFFFFF:
        parser.error("run-token은 uint32 정수여야 합니다")
    if not args.interface or len(args.interface) > 15 or "/" in args.interface or "\0" in args.interface:
        parser.error("잘못된 인터페이스 이름입니다")
    try:
        return run_worker(args)
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
