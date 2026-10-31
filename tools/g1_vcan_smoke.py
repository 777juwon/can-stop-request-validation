#!/usr/bin/env python3
"""G1-only SocketCAN connection smoke check; never a thesis comparison run.

Uses independent sender/receiver processes on an existing, UP vCAN interface.
The 40-slot fixture is deliberately separate from the v1.0 main-test fixtures:
50 ms slots, distance + heartbeat in slots 0..19, heartbeat only in 20..39.
No SUT, stop request, CARLA, physical CAN ACK, or vehicle motion is tested.
Only Python's standard library is required. No interface is created or changed.
"""

from __future__ import annotations

import argparse
from collections import Counter
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


PERIOD_NS = 50_000_000
TOTAL_SLOTS = 40
STOP_SLOT = 20
DISTANCE_ID = 0x100
BACKGROUND_ID = 0x101
CAN_FRAME = struct.Struct("=IB3x8s")
CAN_SFF_MASK = 0x7FF
CAN_EFF_FLAG = 0x80000000
CAN_RTR_FLAG = 0x40000000
CAN_ERR_FLAG = 0x20000000
SCOPE = "G1_ONLY_CONNECTION_SMOKE_NOT_THESIS_COMPARISON"


class CheckFailure(Exception):
    """Recorded transport/fixture assertion failure, not an environment excuse."""


def pack_frame(can_id: int, payload: bytes) -> bytes:
    if not 0 <= can_id <= CAN_SFF_MASK:
        raise ValueError("only standard 11-bit Classic CAN IDs are supported")
    if len(payload) > 8:
        raise ValueError("Classic CAN payload cannot exceed eight bytes")
    return CAN_FRAME.pack(can_id, len(payload), payload.ljust(8, b"\0"))


def unpack_frame(raw: bytes) -> dict:
    if len(raw) != CAN_FRAME.size:
        raise ValueError(f"expected 16-byte Classic CAN frame, got {len(raw)}")
    can_id, dlc, payload = CAN_FRAME.unpack(raw)
    if dlc > 8:
        raise ValueError(f"invalid Classic CAN DLC: {dlc}")
    extended = bool(can_id & CAN_EFF_FLAG)
    return {
        "arbitration_id": can_id & (0x1FFFFFFF if extended else CAN_SFF_MASK),
        "is_extended_id": extended,
        "is_remote_frame": bool(can_id & CAN_RTR_FLAG),
        "is_error_frame": bool(can_id & CAN_ERR_FLAG),
        "dlc": dlc,
        "data_hex": payload[:dlc].hex(),
        "raw_frame_hex": raw.hex(),
    }


def fixture_frames(run_token: int) -> list[dict]:
    """Known byte contract, not a generator of the eighty thesis trial inputs."""
    frames = []
    for slot in range(TOTAL_SLOTS):
        if slot < STOP_SLOT:
            frames.append({
                "slot": slot,
                "arbitration_id": DISTANCE_ID,
                "dlc": 8,
                "data_hex": struct.pack("<HBBI", 1000, slot, 1, run_token).hex(),
            })
        frames.append({
            "slot": slot,
            "arbitration_id": BACKGROUND_ID,
            "dlc": 8,
            "data_hex": struct.pack("<B3xI", slot, run_token).hex(),
        })
    return frames


def validate_link_info(links: list[dict], interface: str) -> dict:
    if len(links) != 1 or links[0].get("ifname") != interface:
        raise OSError(f"cannot identify exactly one requested interface: {interface}")
    link = links[0]
    kind = link.get("linkinfo", {}).get("info_kind")
    if kind != "vcan":
        raise OSError(f"refusing non-vCAN interface {interface}: kind={kind!r}")
    if "UP" not in link.get("flags", []):
        raise OSError(f"interface {interface} is not UP; this tool will not change it")
    return {"ifname": interface, "kind": kind, "flags": link["flags"]}


def claim_output_directory(path: Path) -> None:
    """An existing directory, including an empty one, is never reused."""
    path.mkdir(parents=True, exist_ok=False)


def write_json(path: Path, value: dict | list) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def emit(stream, event: str, **fields) -> None:
    stream.write(json.dumps({"event": event, **fields}, sort_keys=True) + "\n")
    stream.flush()


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def inspect_interface(interface: str, commands: list[dict]) -> dict:
    argv = ["ip", "-details", "-json", "link", "show", "dev", interface]
    begin_ns = time.monotonic_ns()
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        commands.append({"argv": argv, "begin_ns": begin_ns, "error": str(exc)})
        raise OSError(f"interface inspection failed: {exc}") from exc
    record = {
        "argv": argv, "begin_ns": begin_ns, "done_ns": time.monotonic_ns(),
        "exit_code": result.returncode, "stderr": result.stderr,
    }
    commands.append(record)
    if result.returncode:
        raise OSError(f"interface inspection exited {result.returncode}: {result.stderr.strip()}")
    try:
        links = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise OSError("ip returned invalid JSON") from exc
    # Only retain the requested interface's relevant properties, not addresses.
    record["observed_interface"] = validate_link_info(links, interface)
    return record["observed_interface"]


def open_can(interface: str) -> socket.socket:
    if not hasattr(socket, "AF_CAN") or not hasattr(socket, "CAN_RAW"):
        raise OSError("this Python/platform does not provide Linux SocketCAN")
    bus = socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
    try:
        bus.settimeout(0.05)
        bus.bind((interface,))
    except BaseException:
        bus.close()
        raise
    return bus


def sender(interface: str, output: Path, run_token: int) -> dict:
    with open_can(interface) as bus, (output / "sender.jsonl").open("x", encoding="utf-8") as log:
        start_ns = time.monotonic_ns() + 100_000_000
        emit(log, "fixture_start", pid=os.getpid(), start_ns=start_ns,
             period_ns=PERIOD_NS, total_slots=TOTAL_SLOTS, target_stop_slot=STOP_SLOT,
             scope=SCOPE)
        frames = fixture_frames(run_token)
        for slot in range(TOTAL_SLOTS):
            due_ns = start_ns + slot * PERIOD_NS
            while True:
                remaining = due_ns - time.monotonic_ns()
                if remaining <= 0:
                    break
                time.sleep(remaining / 1_000_000_000)
            if slot == STOP_SLOT:
                emit(log, "target_stopped", slot=slot, host_monotonic_ns=time.monotonic_ns(),
                     scheduled_ns=due_ns, background_continues=True)
            for frame in (item for item in frames if item["slot"] == slot):
                raw = pack_frame(frame["arbitration_id"], bytes.fromhex(frame["data_hex"]))
                begin_ns = time.monotonic_ns()
                if begin_ns >= due_ns + PERIOD_NS:
                    emit(log, "missed_slot", slot=slot, scheduled_ns=due_ns,
                         host_monotonic_ns=begin_ns)
                    raise CheckFailure(f"slot {slot} missed; refusing catch-up burst")
                count = bus.send(raw)
                done_ns = time.monotonic_ns()
                emit(log, "tx", slot=slot, scheduled_ns=due_ns, s_begin_ns=begin_ns,
                     s_done_ns=done_ns, bytes_sent=count, pid=os.getpid(), **unpack_frame(raw))
                if count != CAN_FRAME.size:
                    raise CheckFailure(f"partial CAN write: {count}")
        end_ns = start_ns + TOTAL_SLOTS * PERIOD_NS
        remaining = end_ns - time.monotonic_ns()
        if remaining > 0:
            time.sleep(remaining / 1_000_000_000)
        emit(log, "fixture_end", host_monotonic_ns=time.monotonic_ns(), scheduled_ns=end_ns)
    return {"start_ns": start_ns, "scheduled_end_ns": end_ns, "sent_frames": len(frames)}


def receiver(interface: str, output: Path, run_token: int) -> dict:
    del run_token  # The observer records bytes; token selection belongs to the oracle.
    stop = False

    def stop_requested(_signum, _frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, stop_requested)
    signal.signal(signal.SIGINT, stop_requested)
    received = 0
    with open_can(interface) as bus, (output / "receiver.jsonl").open("x", encoding="utf-8") as log:
        # Filter the two fixture IDs; all flags and actual bytes remain observable.
        filters = b"".join(struct.pack("=II", can_id, CAN_SFF_MASK)
                           for can_id in (DISTANCE_ID, BACKGROUND_ID))
        bus.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FILTER, filters)
        ready_ns = time.monotonic_ns()
        write_json(output / "receiver_ready.json", {"pid": os.getpid(), "host_monotonic_ns": ready_ns})
        deadline_ns = ready_ns + 10_000_000_000
        while not stop:
            if time.monotonic_ns() >= deadline_ns:
                raise OSError("receiver did not receive coordinator stop within ten seconds")
            try:
                raw = bus.recv(72)
            except socket.timeout:
                continue
            observed_ns = time.monotonic_ns()
            try:
                decoded = unpack_frame(raw)
            except ValueError as exc:
                emit(log, "decode_error", host_monotonic_ns=observed_ns,
                     raw_frame_hex=raw.hex(), error=str(exc), pid=os.getpid())
            else:
                emit(log, "rx", host_monotonic_ns=observed_ns, pid=os.getpid(), **decoded)
            received += 1
        emit(log, "observer_end", host_monotonic_ns=time.monotonic_ns(), received_frames=received)
    return {"received_frames": received, "stop_requested": stop}


def frame_key(frame: dict) -> tuple:
    return (frame["arbitration_id"], frame["dlc"], frame["data_hex"])


def interval_summary(times: list[int]) -> dict:
    intervals = [right - left for left, right in zip(times, times[1:])]
    return {"samples": len(times), "min_ns": min(intervals) if intervals else None,
            "max_ns": max(intervals) if intervals else None, "intervals_ns": intervals}


def evaluate_observations(tx_events: list[dict], rx_events: list[dict], run_token: int) -> dict:
    """Evaluate actual byte observations against a separately defined G1 fixture.

    Synthetic inputs to this pure function are unit checks only, never G1 proof.
    50 ms is a nominal slot period. Any missed slot fails; actual intervals are
    reported without silently imposing a new thesis response-time tolerance.
    """
    failures = []
    expected = fixture_frames(run_token)
    tx = [event for event in tx_events if event.get("event") == "tx"]
    token_hex = struct.pack("<I", run_token).hex()
    rx = [event for event in rx_events if event.get("event") == "rx"
          and event.get("data_hex", "")[-8:] == token_hex]

    def check(condition: bool, code: str, **details):
        if not condition:
            failures.append({"code": code, **details})

    check(Counter((item["slot"], *frame_key(item)) for item in tx)
          == Counter((item["slot"], *frame_key(item)) for item in expected),
          "sender_fixture_mismatch", expected_count=len(expected), actual_count=len(tx))
    check(Counter(frame_key(item) for item in rx) == Counter(frame_key(item) for item in expected),
          "observer_frame_mismatch", expected_count=len(expected), actual_count=len(rx))
    check([frame_key(item) for item in rx] == [frame_key(item) for item in expected],
          "observer_frame_order_mismatch")
    check(not any(item.get("event") == "decode_error" for item in rx_events), "observer_decode_error")
    check(not any(item.get("event") == "missed_slot" for item in tx_events), "sender_missed_slot")
    for item in tx + rx:
        try:
            raw_fields = unpack_frame(bytes.fromhex(item["raw_frame_hex"]))
        except (KeyError, ValueError) as exc:
            check(False, "raw_frame_invalid", error=str(exc))
        else:
            check(all(item.get(key) == value for key, value in raw_fields.items()),
                  "raw_frame_fields_disagree", arbitration_id=item["arbitration_id"])
        check(not any(item.get(flag, False) for flag in
                      ("is_extended_id", "is_remote_frame", "is_error_frame")),
              "non_standard_data_frame", arbitration_id=item["arbitration_id"])
    starts = [item for item in tx_events if item.get("event") == "fixture_start"]
    ends = [item for item in tx_events if item.get("event") == "fixture_end"]
    stops = [item for item in tx_events if item.get("event") == "target_stopped"]
    check(len(starts) == len(ends) == len(stops) == 1, "fixture_boundaries_missing")
    start_ns = starts[0]["start_ns"] if len(starts) == 1 else None
    for item in tx:
        correct_due = start_ns is not None and item["scheduled_ns"] == start_ns + item["slot"] * PERIOD_NS
        check(correct_due and item["scheduled_ns"] <= item["s_begin_ns"] < item["scheduled_ns"] + PERIOD_NS,
              "sender_outside_nominal_slot", slot=item["slot"])
        check(item["s_done_ns"] >= item["s_begin_ns"] and item["bytes_sent"] == CAN_FRAME.size,
              "sender_write_incomplete", slot=item["slot"])
    tx_by_key = {frame_key(item): item for item in tx}
    for item in rx:
        matching_tx = tx_by_key.get(frame_key(item))
        if matching_tx is not None:
            check(item["host_monotonic_ns"] >= matching_tx["s_begin_ns"],
                  "observation_precedes_send_call", arbitration_id=item["arbitration_id"])
    check(all(right["host_monotonic_ns"] >= left["host_monotonic_ns"]
              for left, right in zip(rx, rx[1:])), "observer_time_order_invalid")
    bg = [item for item in rx if item["arbitration_id"] == BACKGROUND_ID]
    post_stop = [item for item in bg if item["data_hex"] and int(item["data_hex"][:2], 16) >= STOP_SLOT]
    check(len(post_stop) == TOTAL_SLOTS - STOP_SLOT, "background_during_target_stop_missing")
    # Use the observer's ordered post-stop heartbeat stream, rather than mixing
    # sender and receiver timestamps to mistake an already queued frame for a new send.
    pause_observed_ns = post_stop[0]["host_monotonic_ns"] if post_stop else None
    first_post_index = rx.index(post_stop[0]) if post_stop else len(rx)
    check(not any(item["arbitration_id"] == DISTANCE_ID for item in rx[first_post_index:]),
          "target_observed_after_post_stop_heartbeat")
    tx_background = [item["s_begin_ns"] for item in tx if item["arbitration_id"] == BACKGROUND_ID]
    return {
        "status": "PASS" if not failures else "FAIL", "scope": SCOPE,
        "failures": failures, "expected_target_frames": STOP_SLOT,
        "expected_background_frames": TOTAL_SLOTS, "observed_fixture_frames": len(rx),
        "ignored_other_token_frames": sum(item.get("event") == "rx" for item in rx_events) - len(rx),
        "nominal_period_ns": PERIOD_NS,
        "timing_interpretation": "50 ms nominal slots; each send must start within its slot; actual intervals retained",
        "sender_background_intervals": interval_summary(tx_background),
        "observer_background_intervals": interval_summary([item["host_monotonic_ns"] for item in bg]),
        "observer_target_free_window_ns": (post_stop[-1]["host_monotonic_ns"] - pause_observed_ns)
        if post_stop else None,
        "main_comparison_runs_executed": 0,
        "G2": "NOT_RUN", "G3": "NOT_RUN", "G4": "NOT_RUN",
    }


def worker_main(role: str, interface: str, output: Path, run_token: int) -> int:
    begin_ns = time.monotonic_ns()
    result = {"role": role, "pid": os.getpid(), "begin_ns": begin_ns, "scope": SCOPE}
    try:
        # Also refuse physical interfaces if an internal worker is invoked directly.
        checks = []
        result["interface"] = inspect_interface(interface, checks)
        result["preflight_commands"] = checks
        result["observations"] = (sender if role == "sender" else receiver)(interface, output, run_token)
        result["status"] = "COMPLETE"
    except CheckFailure as exc:
        result.update(status="FAIL", error=str(exc))
    except OSError as exc:
        result.update(status="ENV_ERROR", error=str(exc))
    except Exception as exc:
        result.update(status="TOOL_ERROR", error=f"{type(exc).__name__}: {exc}")
    result["done_ns"] = time.monotonic_ns()
    write_json(output / f"{role}_result.json", result)
    return {"COMPLETE": 0, "FAIL": 1, "ENV_ERROR": 2, "TOOL_ERROR": 3}[result["status"]]


def run(interface: str, output: Path, argv: list[str]) -> int:
    claim_output_directory(output)
    run_token = secrets.randbits(32)
    begin_ns = time.monotonic_ns()
    write_json(output / "metadata.json", {
        "scope": SCOPE, "argv": argv, "python": sys.version, "python_executable": sys.executable,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "host_clock": "time.monotonic_ns", "begin_ns": begin_ns,
        "interface": interface, "run_token": run_token, "coordinator_pid": os.getpid(),
        "fixture": {"period_ns": PERIOD_NS, "total_slots": TOTAL_SLOTS,
                    "target_slots": [0, STOP_SLOT - 1], "background_slots": [0, TOTAL_SLOTS - 1],
                    "target_stop_slots": [STOP_SLOT, TOTAL_SLOTS - 1]},
        "fixture_notice": "Connection-only G1 fixture; not v1.0 T-01..T-04 or any of eighty main trials",
        "physical_CAN_ACK_tested": False, "CARLA_executed": False,
        "main_comparison_runs_executed": 0,
    })
    commands = []
    children = []
    process_logs = []
    verdict = {"scope": SCOPE, "status": "TOOL_ERROR"}

    def launch(role: str) -> subprocess.Popen:
        child_argv = [sys.executable, "-I", str(Path(__file__).resolve()), "--interface", interface,
                      "--output-dir", str(output), "--worker", role, "--run-token", str(run_token)]
        log = (output / f"{role}_process.log").open("x", encoding="utf-8")
        process_logs.append(log)
        launch_ns = time.monotonic_ns()
        proc = subprocess.Popen(child_argv, stdout=log, stderr=subprocess.STDOUT)
        children.append(proc)
        commands.append({"role": role, "argv": child_argv, "pid": proc.pid,
                         "begin_ns": launch_ns})
        return proc

    def worker_failure(role: str, code: int):
        path = output / f"{role}_result.json"
        details = json.loads(path.read_text()) if path.exists() else {"exit_code": code}
        status = details.get("status", "TOOL_ERROR")
        if status == "ENV_ERROR":
            raise OSError(f"{role}: {details}")
        if status == "FAIL":
            raise CheckFailure(f"{role}: {details}")
        raise RuntimeError(f"{role}: {details}")

    try:
        inspect_interface(interface, commands)
        rx = launch("receiver")
        ready_deadline = time.monotonic() + 5
        while not (output / "receiver_ready.json").exists():
            if rx.poll() is not None:
                worker_failure("receiver", rx.returncode)
            if time.monotonic() >= ready_deadline:
                raise OSError("receiver readiness deadline exceeded")
            time.sleep(0.01)
        tx = launch("sender")
        try:
            tx_code = tx.wait(timeout=8)
        except subprocess.TimeoutExpired as exc:
            raise CheckFailure("sender did not complete its two-second fixture within eight seconds") from exc
        if tx_code:
            worker_failure("sender", tx_code)
        time.sleep(0.25)  # Retain tail evidence before asking the observer to close.
        if rx.poll() is not None:
            worker_failure("receiver", rx.returncode)
        rx.send_signal(signal.SIGTERM)
        try:
            rx_code = rx.wait(timeout=2)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("receiver did not close after coordinator stop") from exc
        if rx_code:
            worker_failure("receiver", rx_code)
        verdict = evaluate_observations(read_jsonl(output / "sender.jsonl"),
                                        read_jsonl(output / "receiver.jsonl"), run_token)
    except CheckFailure as exc:
        verdict.update(status="FAIL", error=str(exc))
    except OSError as exc:
        verdict.update(status="ENV_ERROR", error=str(exc))
    except KeyboardInterrupt:
        verdict.update(status="INTERRUPTED", error="interrupted; no G1 success claimed")
    except Exception as exc:
        verdict.update(status="TOOL_ERROR", error=f"{type(exc).__name__}: {exc}")
    finally:
        for proc in children:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
        for record in commands:
            if "pid" in record:
                proc = next(child for child in children if child.pid == record["pid"])
                record["exit_code"] = proc.returncode
        for log in process_logs:
            log.close()
        verdict.update(interface=interface, run_token=run_token, begin_ns=begin_ns,
                       done_ns=time.monotonic_ns(), main_comparison_runs_executed=0)
        write_json(output / "commands.json", commands)
        write_json(output / "verdict.json", verdict)
    print(json.dumps({"status": verdict["status"], "output_dir": str(output), "scope": SCOPE}))
    return {"PASS": 0, "FAIL": 1, "ENV_ERROR": 2, "TOOL_ERROR": 3, "INTERRUPTED": 130}[verdict["status"]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interface", default="vcan0", help="existing UP vCAN interface; never modified")
    parser.add_argument("--output-dir", required=True, type=Path, help="new evidence directory; must not exist")
    parser.add_argument("--worker", choices=("sender", "receiver"), help=argparse.SUPPRESS)
    parser.add_argument("--run-token", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not args.interface or len(args.interface) > 15 or "/" in args.interface:
        parser.error("invalid interface name")
    output = args.output_dir.absolute()
    if args.worker:
        if args.run_token is None or not 0 <= args.run_token <= 0xFFFFFFFF:
            parser.error("internal worker requires a uint32 run token")
        return worker_main(args.worker, args.interface, output, args.run_token)

    def terminated(_signum, _frame):
        # Keep coordinator evidence and child cleanup on timeout-wrapper SIGTERM.
        # The receiver worker installs its own graceful-stop handler separately.
        raise KeyboardInterrupt("SIGTERM")

    previous_sigterm = signal.signal(signal.SIGTERM, terminated)
    try:
        command = [sys.executable, str(Path(__file__).resolve()), *(sys.argv[1:] if argv is None else argv)]
        return run(args.interface, output, command)
    except FileExistsError:
        print(f"refusing existing output directory: {output}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"cannot create/write evidence directory: {exc}", file=sys.stderr)
        return 2
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)


if __name__ == "__main__":
    raise SystemExit(main())
