#!/usr/bin/env python3
"""G3의 첫 단계: CARLA 없이 StopRequest 바이트와 독립 vCAN 송수신을 확인한다.

stop=0 다섯 개와 stop=1 다섯 개는 연결 확인용 입력이다. SUT의 판단,
adapter의 오류 대응, CARLA 제어, 정지 잠금이나 본시험을 구현하지 않는다.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import struct
import subprocess
import sys
import time
import traceback


SCOPE = "G3_STAGE1_REQUEST_TRANSPORT_ONLY"
STOP_ID = 0x200
PERIOD_NS = 50_000_000
SLOTS = 10
PAYLOAD = struct.Struct("<BBBBI")
CAN_FRAME = struct.Struct("=IB3x8s")
EXIT_CODES = {"PASS": 0, "FAIL": 1, "ENV_ERROR": 2,
              "TOOL_ERROR": 3, "INPUT_ERROR": 4, "INTERRUPTED": 130}


class InputFailure(Exception):
    """지정한 송신 슬롯을 지키지 못한 시험 입력의 실패를 나타낸다."""


class WorkerFailure(Exception):
    """독립 작업 프로세스가 기록한 실패 분류를 상위 실행에 전달한다."""

    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


def encode_request(stop: int, reason: int, counter: int, run_token: int) -> bytes:
    """정수 필드를 전송 형식으로 만든다. 값의 의미적 유효성은 판정하지 않는다."""
    for name, value, maximum in (("stop", stop, 255), ("reason", reason, 255),
                                 ("counter", counter, 255), ("run_token", run_token, 0xFFFFFFFF)):
        if type(value) is not int or not 0 <= value <= maximum:
            raise ValueError(f"{name}: 0~{maximum} 범위의 정수가 필요합니다")
    return PAYLOAD.pack(stop, reason, counter, 0, run_token)


def decode_request(payload: bytes) -> dict:
    """8바이트의 필드를 읽는다. 미정의 값과 예약 byte도 진단용으로 보존한다.

    이 함수의 반환은 adapter가 요청을 유효하다고 인정했다는 뜻이 아니다.
    stop/reason의 모순, token 혼입과 재생에 대한 후속 동작은 정하지 않는다.
    """
    if len(payload) != 8:
        raise ValueError("StopRequest payload는 정확히 8바이트여야 합니다")
    stop, reason, counter, reserved, token = PAYLOAD.unpack(payload)
    return {"stop": stop, "reason": reason, "counter": counter,
            "reserved": reserved, "run_token": token}


def frame_fields(raw: bytes) -> dict:
    """Classic CAN 프레임의 실제 길이, 플래그와 payload를 보존한다."""
    if len(raw) != CAN_FRAME.size:
        raise ValueError(f"Classic CAN 프레임 길이 불일치: {len(raw)}")
    can_id, dlc, data = CAN_FRAME.unpack(raw)
    if dlc > 8:
        raise ValueError(f"Classic CAN DLC 불일치: {dlc}")
    return {"arbitration_id": can_id & 0x1FFFFFFF, "dlc": dlc,
            "extended": bool(can_id & 0x80000000), "remote": bool(can_id & 0x40000000),
            "error_frame": bool(can_id & 0x20000000), "data_hex": data[:dlc].hex(),
            "raw_frame_hex": raw.hex()}


def write_json(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def emit(stream, **fields) -> None:
    stream.write(json.dumps(fields, ensure_ascii=False, allow_nan=False) + "\n")
    stream.flush()


def read_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def validate_link(links: list[dict], interface: str) -> dict:
    """이미 존재하는 UP 상태의 가상 CAN만 사용하고 장치를 변경하지 않는다."""
    if len(links) != 1 or links[0].get("ifname") != interface:
        raise OSError("요청한 인터페이스를 하나로 식별하지 못했습니다")
    link = links[0]
    if link.get("linkinfo", {}).get("info_kind") != "vcan" or "UP" not in link.get("flags", []):
        raise OSError("UP 상태의 vcan 인터페이스만 사용할 수 있습니다")
    return link


def inspect_link(interface: str, output: Path, record_name="preflight.json") -> dict:
    argv = ["ip", "-details", "-json", "link", "show", "dev", interface]
    result = subprocess.run(argv, capture_output=True, text=True, timeout=5)
    write_json(output / record_name, {"command": argv, "exit_code": result.returncode,
                                          "stdout": result.stdout, "stderr": result.stderr})
    if result.returncode:
        raise OSError(result.stderr.strip())
    return validate_link(json.loads(result.stdout), interface)


def open_bus(interface: str):
    bus = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
    try:
        bus.settimeout(0.05)
        bus.bind((interface,))
    except BaseException:
        bus.close()
        raise
    return bus


def send_fixture(interface: str, output: Path, token: int) -> dict:
    with open_bus(interface) as bus, (output / "sender.jsonl").open("x") as stream:
        start = time.monotonic_ns() + 100_000_000
        for index in range(SLOTS):
            due = start + index * PERIOD_NS
            remaining = (due - time.monotonic_ns()) / 1e9
            if remaining > 0:
                time.sleep(remaining)
            active = int(index >= 5)
            raw = CAN_FRAME.pack(STOP_ID, 8, encode_request(active, active, index, token))
            begin = time.monotonic_ns()
            if begin >= due + PERIOD_NS:
                emit(stream, event="missed_slot", slot=index, scheduled_ns=due,
                     host_monotonic_ns=begin)
                raise InputFailure(f"송신 슬롯 {index}를 놓쳐 밀린 입력을 전송하지 않습니다")
            sent = bus.send(raw)
            done = time.monotonic_ns()
            emit(stream, event="tx", pid=os.getpid(), slot=index, scheduled_ns=due,
                 s_begin_ns=begin, s_done_ns=done, bytes_sent=sent, **frame_fields(raw))
            if sent != CAN_FRAME.size:
                raise InputFailure("CAN 프레임 일부만 전송됐습니다")
    return {"sent_frames": SLOTS}


def receive_frames(interface: str, output: Path) -> dict:
    stop = False

    def stop_requested(_signum, _frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, stop_requested)
    signal.signal(signal.SIGINT, stop_requested)
    count = 0
    with open_bus(interface) as bus, (output / "receiver.jsonl").open("x") as stream:
        # 같은 하위 ID에 잘못된 플래그가 붙은 경우도 로그에 남긴다.
        bus.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FILTER, struct.pack("=II", STOP_ID, 0x7FF))
        ready = time.monotonic_ns()
        write_json(output / "receiver_ready.json", {"pid": os.getpid(), "host_monotonic_ns": ready})
        while not stop:
            if time.monotonic_ns() - ready >= 10_000_000_000:
                raise OSError("수신기 종료 신호를 10초 안에 받지 못했습니다")
            try:
                raw = bus.recv(72)
            except socket.timeout:
                continue
            observed = time.monotonic_ns()
            event = {"event": "rx", "pid": os.getpid(), "host_monotonic_ns": observed,
                     "raw_frame_hex": raw.hex()}
            try:
                event.update(frame_fields(raw))
                event["fields"] = decode_request(bytes.fromhex(event["data_hex"]))
            except ValueError as exc:
                event["decode_error"] = str(exc)
            emit(stream, **event)
            count += 1
    return {"received_frames": count}


def evaluate(tx: list[dict], rx: list[dict], token: int, ready_ns: int, ended_ns: int) -> dict:
    """송수신 도구의 내부 성공 선언 대신 별도로 구성한 바이트와 비교한다."""
    failures = []
    expected = [(bytes([int(i >= 5), int(i >= 5), i, 0]) + token.to_bytes(4, "little")).hex()
                for i in range(SLOTS)]
    if len(tx) != SLOTS or len(rx) != SLOTS:
        failures.append("송수신 프레임 수가 각각 10개여야 합니다")
    for label, events in (("tx", tx), ("rx", rx)):
        if [e.get("data_hex") for e in events] != expected:
            failures.append(f"{label}: 기대 payload 또는 순서 불일치")
        for event in events:
            try:
                raw = bytes.fromhex(event["raw_frame_hex"])
                frame = frame_fields(raw)
                if not all(event.get(key) == value for key, value in frame.items()):
                    raise ValueError("원시 프레임과 로그 해석이 다릅니다")
                if frame["arbitration_id"] != STOP_ID or frame["dlc"] != 8:
                    raise ValueError("요청 ID 또는 DLC 불일치")
                if any(frame[key] for key in ("extended", "remote", "error_frame")):
                    raise ValueError("표준 데이터 프레임 이외의 플래그")
                if label == "rx":
                    # parser의 선언을 신뢰하지 않고 원시 바이트에서 다시 읽는다.
                    b = raw[8:16]
                    expected_fields = {"stop": b[0], "reason": b[1], "counter": b[2],
                                       "reserved": b[3], "run_token": int.from_bytes(b[4:], "little")}
                    if event["fields"] != expected_fields or "decode_error" in event:
                        raise ValueError("수신 payload 해석 불일치")
                    if not ready_ns <= event["host_monotonic_ns"] <= ended_ns:
                        raise ValueError("수신 시각 경계 불일치")
                else:
                    if event["bytes_sent"] != 16:
                        raise ValueError("불완전한 전송 길이")
                    if not ready_ns <= event["scheduled_ns"] <= event["s_begin_ns"] <= event["s_done_ns"] <= ended_ns:
                        raise ValueError("송신 시각 경계 불일치")
                    if event["s_begin_ns"] >= event["scheduled_ns"] + PERIOD_NS:
                        raise ValueError("송신 슬롯의 상한 초과")
            except (KeyError, ValueError, TypeError):
                failures.append(f"{label}: 원시 프레임, 해석 또는 시각 불일치")
                break
    for index, (sent, received) in enumerate(zip(tx, rx)):
        if sent.get("slot") != index or received.get("host_monotonic_ns", -1) < sent.get("s_begin_ns", 0):
            failures.append("송신 슬롯 또는 수신 시각 경계 불일치")
    if tx and any(e.get("scheduled_ns") != tx[0].get("scheduled_ns", 0) + i * PERIOD_NS
                  for i, e in enumerate(tx)):
        failures.append("50 ms 명목 송신 슬롯 간격 불일치")
    for events, key in ((tx, "s_begin_ns"), (rx, "host_monotonic_ns")):
        if any(b.get(key, -1) < a.get(key, 0) for a, b in zip(events, events[1:])):
            failures.append("호스트 관측 시각의 순서 불일치")
    return {"status": "FAIL" if failures else "PASS", "scope": SCOPE, "failures": failures,
            "transmitted_frames": len(tx), "observed_frames": len(rx),
            "full_g3_verified": False, "carla_executed": False, "main_trials_executed": 0}


def run_worker(args) -> int:
    result = {"pid": os.getpid(), "role": args.worker, "status": "COMPLETE"}
    try:
        # 숨김 worker 옵션을 직접 호출해도 물리 CAN을 사용할 수 없게 한다.
        inspect_link(args.interface, args.output_dir, record_name=f"{args.worker}_preflight.json")
        if args.worker == "sender":
            result.update(send_fixture(args.interface, args.output_dir, args.run_token))
        else:
            result.update(receive_frames(args.interface, args.output_dir))
    except (Exception, KeyboardInterrupt) as exc:
        result.update(status="INPUT_ERROR" if isinstance(exc, InputFailure) else
                      "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else
                      "ENV_ERROR" if isinstance(exc, OSError) else "TOOL_ERROR",
                      error=str(exc))
        (args.output_dir / f"{args.worker}_error.txt").write_text(traceback.format_exc())
    write_json(args.output_dir / f"{args.worker}_result.json", result)
    return 0 if result["status"] == "COMPLETE" else EXIT_CODES[result["status"]]


def early_worker_failure(output: Path, role: str, code: int) -> WorkerFailure:
    """조기 종료를 모두 환경 오류로 바꾸지 않고 남은 원인을 확인한다."""
    try:
        result = json.loads((output / f"{role}_result.json").read_text())
        status = result["status"]
        if status not in ("FAIL", "ENV_ERROR", "TOOL_ERROR", "INPUT_ERROR", "INTERRUPTED") or EXIT_CODES[status] != code:
            status = "TOOL_ERROR"
        return WorkerFailure(status, f"{role} 조기 종료: {result.get('error', result['status'])}")
    except (OSError, ValueError, KeyError):
        return WorkerFailure("TOOL_ERROR", f"{role} 조기 종료: 판정 기록 없음, 종료코드 {code}")


def coordinate(args) -> int:
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    token = secrets.randbits(32)
    commands, children, handles = [], {}, []
    result = {"scope": SCOPE, "status": "ENV_ERROR", "full_g3_verified": False,
              "carla_executed": False, "main_trials_executed": 0, "cleanup_errors": []}
    source = Path(__file__).resolve()
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source.parent.parent,
                                capture_output=True, text=True, check=True).stdout.strip()
        write_json(output / "metadata.json", {"baseline": "v1.0", "scope": SCOPE,
                   "run_id": output.name, "run_token": token, "git_commit": commit,
                   "tool_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                   "started_utc": datetime.now(timezone.utc).isoformat(),
                   "python": sys.version, "command_arguments": sys.argv[1:],
                   "fixture": "연결 확인용: 정상 5개와 NEAR_DISTANCE 5개, counter 0~9, 50 ms",
                   "interface": args.interface})
        result["interface"] = inspect_link(args.interface, output)

        def start(role):
            argv = [sys.executable, "-I", str(source), "--worker", role, "--interface", args.interface,
                    "--output-dir", str(output), "--run-token", str(token)]
            handle = (output / f"{role}_stderr.txt").open("x")
            handles.append(handle)
            child = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=handle)
            children[role] = child
            commands.append({"role": role, "argv": argv, "pid": child.pid})
            return child

        receiver = start("receiver")
        deadline = time.monotonic() + 3
        while not (output / "receiver_ready.json").exists():
            if receiver.poll() is not None:
                raise early_worker_failure(output, "receiver", receiver.returncode)
            if time.monotonic() >= deadline:
                raise OSError("수신기가 준비되지 않았습니다")
            time.sleep(0.01)
        sender = start("sender")
        sender_code = sender.wait(timeout=3)
        time.sleep(0.1)
        if receiver.poll() is not None:
            raise early_worker_failure(output, "receiver", receiver.returncode)
        receiver.terminate()
        receiver_code = receiver.wait(timeout=3)
        ended = time.monotonic_ns()
        ready = json.loads((output / "receiver_ready.json").read_text())
        worker_results = {role: json.loads((output / f"{role}_result.json").read_text())
                          for role in ("sender", "receiver")}
        if sender_code or receiver_code:
            statuses = [r["status"] for r in worker_results.values()]
            result["status"] = next((s for s in ("TOOL_ERROR", "INPUT_ERROR", "INTERRUPTED", "ENV_ERROR")
                                     if s in statuses), "TOOL_ERROR")
            result["worker_results"] = worker_results
        else:
            result.update(evaluate(read_events(output / "sender.jsonl"),
                                   read_events(output / "receiver.jsonl"), token,
                                   ready["host_monotonic_ns"], ended))
            if (sender.pid == receiver.pid or any(worker_results[role]["pid"] != children[role].pid
                                                 for role in children)):
                result.update(status="FAIL", error="독립 프로세스 식별이 일치하지 않습니다")
        result["worker_exit_codes"] = {"sender": sender_code, "receiver": receiver_code}
    except (Exception, KeyboardInterrupt) as exc:
        result.update(status=exc.status if isinstance(exc, WorkerFailure) else
                      "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else
                      "ENV_ERROR" if isinstance(exc, (OSError, subprocess.TimeoutExpired)) else "TOOL_ERROR",
                      error=str(exc))
        (output / "error.txt").write_text(traceback.format_exc())
    finally:
        for role, child in children.items():
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                    result["cleanup_errors"].append(role + ": 종료 유예 초과")
        for handle in handles:
            handle.close()
        if result["status"] == "PASS" and result["cleanup_errors"]:
            result["status"] = "TOOL_ERROR"
        result.setdefault("worker_exit_codes", {role: child.poll() for role, child in children.items()})
        write_json(output / "commands.json", commands)
        write_json(output / "verdict.json", result)
    print(json.dumps({"status": result["status"], "scope": SCOPE, "output_dir": str(output)}))
    return EXIT_CODES[result["status"]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interface", default="vcan0", help="이미 준비된 UP 상태의 vcan 장치")
    parser.add_argument("--output-dir", required=True, type=Path, help="존재하지 않는 새 증거 폴더")
    parser.add_argument("--worker", choices=("sender", "receiver"), help=argparse.SUPPRESS)
    parser.add_argument("--run-token", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        if args.run_token is None or not 0 <= args.run_token <= 0xFFFFFFFF:
            parser.error("worker에는 uint32 run-token이 필요합니다")
        return run_worker(args)

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt("종료 신호")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        return coordinate(args)
    except FileExistsError:
        print("증거 폴더가 이미 존재합니다. 새 run ID를 사용하세요.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
