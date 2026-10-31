#!/usr/bin/env python3
"""G3 통합 실행의 독립 CAN 송신기와 관측기다.

정상 5개, 정지 5개, 정상 복원 10개는 연결 확인용 fixture다.
논문 본시험이나 SUT 판단을 구현하지 않는다. 이 파일은 CARLA를 호출하지
않으며, coordinator가 만든 전용 증거 폴더와 시작 신호를 사용한다.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import sys
import time
import traceback


# -I의 외부 경로 차단을 유지하며 이 저장소의 tools 패키지만 명시한다.
REPOSITORY = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY))
from tools.g3_request_smoke import (  # noqa: E402
    CAN_FRAME, InputFailure, emit, encode_request, frame_fields, inspect_link, open_bus, write_json,
)


SCOPE = "G3_INTEGRATION_CAN_FIXTURE_ONLY"
PERIOD_NS = 50_000_000
SLOTS = 20
START_WAIT_NS = 35_000_000_000
WATCHDOG_NS = 45_000_000_000
EXIT_CODES = {"COMPLETE": 0, "ENV_ERROR": 2, "TOOL_ERROR": 3,
              "INPUT_ERROR": 4, "INTERRUPTED": 130}


@dataclass
class StopSignals:
    """관측기의 정상 종료와 사용자의 취소를 구분해 기록한다."""

    terminate_requested: bool = False
    interrupt_requested: bool = False
    signal_number: int | None = None

    def handler(self, number, _frame) -> None:
        self.signal_number = number
        if number == signal.SIGTERM:
            self.terminate_requested = True
        else:
            self.interrupt_requested = True

    def check_sender(self) -> None:
        if self.terminate_requested or self.interrupt_requested:
            raise KeyboardInterrupt("송신 완료 전 종료 신호")


def fixture_payloads(token: int) -> list[bytes]:
    """기준선의 StopRequest 배치로 G3 연결 확인 입력 20개를 만든다."""
    return [encode_request(int(5 <= i < 10), int(5 <= i < 10), i, token)
            for i in range(SLOTS)]


def sleep_until(due_ns: int, signals: StopSignals, watchdog_ns: int) -> None:
    """취소와 watchdog을 확인하며 명목 슬롯까지 기다린다."""
    while True:
        signals.check_sender()
        now = time.monotonic_ns()
        if now >= watchdog_ns:
            raise OSError("송신기 45초 watchdog 초과")
        if now >= due_ns:
            return
        time.sleep(min((due_ns - now) / 1e9, 0.05))


def sender(interface: str, output: Path, token: int, signals: StopSignals) -> dict:
    """차량 준비 신호 이후에만 송신하고 실제 호출 경계를 flush한다."""
    with open_bus(interface) as bus, (output / "input_events.jsonl").open("x", encoding="utf-8") as stream:
        ready = time.monotonic_ns()
        write_json(output / "sender_ready.json", {"pid": os.getpid(), "host_monotonic_ns": ready,
                   "interface": interface, "scope": SCOPE})
        wait_deadline, watchdog = ready + START_WAIT_NS, ready + WATCHDOG_NS
        while True:
            signals.check_sender()
            now = time.monotonic_ns()
            if now >= wait_deadline:
                raise OSError("sender_start.json을 35초 안에 관찰하지 못했습니다")
            if (output / "sender_start.json").is_file():
                start_observed = now
                break
            time.sleep(0.01)
        first_due = time.monotonic_ns() + 100_000_000
        payloads = fixture_payloads(token)
        for slot, payload in enumerate(payloads):
            due = first_due + slot * PERIOD_NS
            sleep_until(due, signals, watchdog)
            raw = CAN_FRAME.pack(0x200, 8, payload)
            begin = time.monotonic_ns()
            if begin >= due + PERIOD_NS:
                emit(stream, event="missed_slot", slot=slot, scheduled_ns=due,
                     host_monotonic_ns=begin)
                raise InputFailure(f"송신 슬롯 {slot}를 놓쳐 밀린 입력을 전송하지 않습니다")
            count = bus.send(raw)
            done = time.monotonic_ns()
            emit(stream, event="tx", slot=slot, scheduled_ns=due, s_begin_ns=begin,
                 s_done_ns=done, bytes_sent=count, pid=os.getpid(), **frame_fields(raw))
            if count != CAN_FRAME.size:
                raise InputFailure("Classic CAN 프레임 일부만 송신됐습니다")
        return {"sent_frames": SLOTS, "ready_monotonic_ns": ready,
                "start_signal_observed_monotonic_ns": start_observed,
                "fixture_first_scheduled_ns": first_due,
                "start_wait_deadline_ns": wait_deadline, "watchdog_deadline_ns": watchdog}


def observer(interface: str, output: Path, signals: StopSignals) -> dict:
    """token으로 솎지 않은 원시 요청과 해석 실패를 별도로 보존한다."""
    count = errors = 0
    with open_bus(interface) as bus, (output / "can_observer.jsonl").open("x", encoding="utf-8") as stream:
        bus.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FILTER, struct.pack("=II", 0x200, 0x7FF))
        ready = time.monotonic_ns()
        watchdog = ready + WATCHDOG_NS
        write_json(output / "observer_ready.json", {"pid": os.getpid(), "host_monotonic_ns": ready,
                   "interface": interface, "scope": SCOPE})
        while True:
            if signals.interrupt_requested:
                raise KeyboardInterrupt("관측기 사용자 취소")
            if time.monotonic_ns() >= watchdog:
                raise OSError("관측기 45초 watchdog 초과")
            if signals.terminate_requested:
                break
            try:
                raw = bus.recv(72)
            except socket.timeout:
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
        return {"received_frames": count, "decode_errors": errors,
                "ready_monotonic_ns": ready, "watchdog_deadline_ns": watchdog,
                "termination": "COORDINATOR_SIGTERM"}


def run_worker(args: argparse.Namespace) -> int:
    """독립 vCAN 사전검사부터 종료 정보까지 이번 worker의 근거를 남긴다."""
    output = args.output_dir.resolve()
    if not output.is_dir():
        raise OSError("coordinator가 새 증거 폴더를 먼저 만들어야 합니다")
    owned = [f"{args.worker}_result.json", f"{args.worker}_ready.json",
             f"{args.worker}_preflight.json", f"{args.worker}_error.txt",
             "input_events.jsonl" if args.worker == "sender" else "can_observer.jsonl"]
    if any(os.path.lexists(output / name) for name in owned):
        raise FileExistsError("기존 worker 증거가 있어 덮어쓰지 않습니다")
    signals = StopSignals()
    previous = {number: signal.signal(number, signals.handler)
                for number in (signal.SIGTERM, signal.SIGINT)}
    result = {"scope": SCOPE, "role": args.worker, "pid": os.getpid(), "status": "TOOL_ERROR",
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "begin_monotonic_ns": time.monotonic_ns(), "interface": args.interface,
              "run_token": args.run_token}
    try:
        inspect_link(args.interface, output, record_name=f"{args.worker}_preflight.json")
        result.update(sender(args.interface, output, args.run_token, signals) if args.worker == "sender"
                      else observer(args.interface, output, signals))
        result["status"] = "COMPLETE"
    except (Exception, KeyboardInterrupt) as exc:
        result.update(status="INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else
                      "INPUT_ERROR" if isinstance(exc, InputFailure) else
                      "ENV_ERROR" if isinstance(exc, (OSError, subprocess.TimeoutExpired)) else "TOOL_ERROR",
                      error=str(exc), error_type=type(exc).__name__)
        with (output / f"{args.worker}_error.txt").open("x", encoding="utf-8") as error_file:
            error_file.write(traceback.format_exc())
    finally:
        result.update(finished_utc=datetime.now(timezone.utc).isoformat(),
                      done_monotonic_ns=time.monotonic_ns(),
                      terminate_requested=signals.terminate_requested,
                      interrupt_requested=signals.interrupt_requested,
                      signal_number=signals.signal_number)
        result["exit_code"] = EXIT_CODES[result["status"]]
        write_json(output / f"{args.worker}_result.json", result)
        for number, old_handler in previous.items():
            signal.signal(number, old_handler)
    return result["exit_code"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=("sender", "observer"), required=True)
    parser.add_argument("--interface", default="vcan0")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-token", type=int, required=True)
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
