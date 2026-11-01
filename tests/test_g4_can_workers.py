"""G4 worker의 바이트, 시간 게이트와 실패 보존 검사다. 실제 CAN 실행은 아니다."""

import json
from pathlib import Path
import signal
import socket
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import g4_can_workers as worker


TOKEN = 0x12345678


def read_events(output, name):
    """검사에서 완성한 JSONL의 각 행을 읽는다."""
    return [json.loads(line) for line in (output / name).read_text().splitlines()]


class FakeClock:
    """실제 대기 없이 호출 순서와 송신 경계를 구분하는 시계다."""

    def __init__(self):
        self.now = 1_000_000_000

    def monotonic_ns(self):
        value = self.now
        self.now += 100
        return value

    def advance(self, duration):
        self.now += duration

    def sleep_until(self, due, signals, watchdog):
        signals.check_sender()
        self.now = max(self.now, due)
        if self.now >= watchdog:
            raise OSError("가짜 watchdog 초과")


class FakeBus:
    """원시 프레임과 필터만 기록하며 실제 소켓을 만들지 않는다."""

    def __init__(self, packets=(), on_receive=None):
        self.sent, self.filters, self.timeout = [], [], None
        self.packets = iter(packets)
        self.on_receive = on_receive

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def send(self, raw):
        self.sent.append(raw)
        return worker.CAN_FRAME.size

    def setsockopt(self, *values):
        self.filters.append(values)

    def settimeout(self, value):
        self.timeout = value

    def recv(self, _size):
        if self.on_receive:
            self.on_receive()
        try:
            return next(self.packets)
        except StopIteration:
            raise socket.timeout()


class FixtureTests(unittest.TestCase):
    def test_t03_exact_count_bytes_and_counter_wrap(self):
        slots = [worker.fixture_frames(TOKEN, 256 + slot, slot) for slot in range(400)]
        frames = [worker.CAN_FRAME.unpack(raw) for packet in slots for raw in packet]
        distance = [payload for can_id, _dlc, payload in frames if can_id == 0x100]
        heartbeat = [payload for can_id, _dlc, payload in frames if can_id == 0x101]
        self.assertEqual(len(distance), 340)
        self.assertEqual(len(heartbeat), 400)
        self.assertEqual(distance[0].hex(), "e803000178563412")
        self.assertEqual(distance[99].hex(), "e803630178563412")
        self.assertEqual(distance[100].hex(), "e803a00178563412")
        self.assertEqual(heartbeat[100].hex(), "6400000078563412")
        self.assertEqual(heartbeat[159].hex(), "9f00000078563412")
        self.assertEqual(heartbeat[255][0], 255)
        self.assertEqual(heartbeat[256][0], 0)
        self.assertTrue(all(dlc == 8 for _can_id, dlc, _payload in frames))
        for slot, packet in enumerate(slots):
            ids = [worker.CAN_FRAME.unpack(raw)[0] for raw in packet]
            self.assertEqual(ids, [0x101] if 100 <= slot < 160 else [0x100, 0x101])

    def test_preparation_counter_is_never_reset(self):
        counters = [worker.CAN_FRAME.unpack(worker.fixture_frames(TOKEN, slot)[0])[2][2]
                    for slot in range(258)]
        self.assertEqual(counters, [slot % 256 for slot in range(258)])
        self.assertEqual([worker.trial_start_slot(slot) for slot in (0, 1, 255, 256, 257, 512)],
                         [256, 256, 256, 256, 512, 512])

    def test_invalid_token_and_discontinuous_trial_are_rejected(self):
        for token in (-1, 0x100000000, True):
            with self.subTest(token=token), self.assertRaises(ValueError):
                worker.fixture_frames(token, 0)
        for token in (0, 0xFFFFFFFF):
            self.assertEqual(worker.CAN_FRAME.unpack(worker.fixture_frames(token, 0)[0])[2][4:],
                             token.to_bytes(4, "little"))
        for args in ((TOKEN, -1, None), (TOKEN, True, None), (TOKEN, 256, 400), (TOKEN, 257, 0)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                worker.fixture_frames(*args)


class EvidenceTests(unittest.TestCase):
    def test_runtime_signal_publication_does_not_force_disk_sync(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "signal.json"
            with patch.object(worker.os, "fsync") as force_sync:
                worker.atomic_write_json(path, {"ready": True})
            force_sync.assert_not_called()
            self.assertEqual(json.loads(path.read_text()), {"ready": True})

    def test_atomic_json_never_overwrites_existing_file_or_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            path = output / "command.json"
            worker.atomic_write_json(path, {"value": 1})
            with self.assertRaises(FileExistsError):
                worker.atomic_write_json(path, {"value": 2})
            self.assertEqual(json.loads(path.read_text()), {"value": 1})
            link = output / "link.json"
            link.symlink_to(path)
            with self.assertRaises(FileExistsError):
                worker.atomic_write_json(link, {"value": 3})
            self.assertTrue(link.is_symlink())
            self.assertEqual(sorted(item.name for item in output.iterdir()), ["command.json", "link.json"])

    def test_command_rejects_stale_wrong_token_and_partial_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "arm.json"
            self.assertIsNone(worker.read_command(path, TOKEN, 100, 200))
            for value in ({"run_token": TOKEN, "host_monotonic_ns": 99},
                          {"run_token": TOKEN + 1, "host_monotonic_ns": 100},
                          {"run_token": TOKEN, "host_monotonic_ns": True}, []):
                path.write_text(json.dumps(value))
                with self.subTest(value=value), self.assertRaises(worker.InputFailure):
                    worker.read_command(path, TOKEN, 100, 200)
            path.write_text('{"run_token":')
            with self.assertRaises(worker.InputFailure):
                worker.read_command(path, TOKEN, 100, 200)
            path.write_text(json.dumps({"run_token": TOKEN, "host_monotonic_ns": 100}))
            self.assertEqual(worker.read_command(path, TOKEN, 100, 200)["run_token"], TOKEN)


class SenderTests(unittest.TestCase):
    def test_start_signal_after_both_frames_preserves_slot_when_publication_is_slow(self):
        with tempfile.TemporaryDirectory() as directory:
            output, clock, bus = Path(directory), FakeClock(), FakeBus()
            worker.write_json(output / "trial_requested.json", {"run_token": TOKEN, "host_monotonic_ns": clock.now})
            publish = worker.atomic_write_json

            def slow_signal(path, value):
                if path.name == "trial_started.json":
                    # 준비512개와 본 슬롯0의 거리/심박2개가 먼저 송신돼야 한다.
                    self.assertEqual(len(bus.sent), 514)
                    self.assertEqual([worker.CAN_FRAME.unpack(packet)[0] for packet in bus.sent[-2:]], [0x100, 0x101])
                    clock.advance(60_000_000)
                return publish(path, value)

            with patch.object(worker, "open_bus", return_value=bus), \
                    patch.object(worker, "sleep_until", side_effect=clock.sleep_until), \
                    patch.object(worker.time, "monotonic_ns", side_effect=clock.monotonic_ns), \
                    patch.object(worker, "atomic_write_json", side_effect=slow_signal):
                result = worker.sender("vcan0", output, TOKEN, worker.StopSignals(), "T-01")
            trial = [row for row in read_events(output, "input_events.jsonl") if row["event"] == "tx" and row["phase"] == "trial"]
            self.assertEqual(result["trial_distance_frames"], 400)
            self.assertEqual(result["trial_heartbeat_frames"], 400)
            self.assertEqual([row["arbitration_id"] for row in trial[:2]], [0x100, 0x101])
            self.assertTrue(all(row["s_begin_ns"] < row["scheduled_ns"] + worker.PERIOD_NS for row in trial))
            marker = json.loads((output / "trial_started.json").read_text())
            self.assertEqual(marker["t0_ns"], trial[0]["s_begin_ns"])

    def test_sender_preserves_preparation_and_anchors_trial_to_actual_first_send(self):
        with tempfile.TemporaryDirectory() as directory:
            output, clock, bus = Path(directory), FakeClock(), FakeBus()
            worker.write_json(output / "trial_requested.json", {"run_token": TOKEN, "host_monotonic_ns": clock.now})
            with patch.object(worker, "open_bus", return_value=bus), \
                    patch.object(worker, "sleep_until", side_effect=clock.sleep_until), \
                    patch.object(worker.time, "monotonic_ns", side_effect=clock.monotonic_ns):
                result = worker.sender("vcan0", output, TOKEN, worker.StopSignals())
            events = read_events(output, "input_events.jsonl")
            sent = [event for event in events if event["event"] == "tx"]
            preparation = [event for event in sent if event["phase"] == "prepare"]
            trial = [event for event in sent if event["phase"] == "trial"]
            self.assertEqual(len(preparation), 512)
            self.assertTrue(all(event["slot"] is None for event in preparation))
            self.assertEqual(result["trial_distance_frames"], 340)
            self.assertEqual(result["trial_heartbeat_frames"], 400)
            self.assertEqual(len(trial), 740)
            self.assertEqual(len([event for event in events if event["event"] == "distance_omitted"]), 60)
            marker = json.loads((output / "trial_started.json").read_text())
            self.assertEqual(marker["trial_global_slot"], 256)
            self.assertEqual(marker["t0_ns"], trial[0]["s_begin_ns"])
            self.assertEqual(marker["t0_done_ns"], trial[0]["s_done_ns"])
            self.assertEqual(marker["trial_first_scheduled_ns"], marker["t0_ns"])
            self.assertGreater(trial[0]["s_begin_ns"], trial[0]["planned_due_ns"])
            for event in trial:
                self.assertEqual(event["scheduled_ns"], marker["t0_ns"] + event["slot"] * worker.PERIOD_NS)
                self.assertEqual(event["global_slot"], 256 + event["slot"])
                self.assertLessEqual(event["scheduled_ns"], event["s_begin_ns"])
                self.assertLessEqual(event["s_begin_ns"], event["s_done_ns"])
            self.assertGreaterEqual(clock.now, marker["trial_end_ns"])
            self.assertEqual(result["sent_frames"], len(bus.sent))

    def test_missed_preparation_slot_never_sends_catchup_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            output, clock, bus = Path(directory), FakeClock(), FakeBus()

            def delayed_sleep(due, _signals, _watchdog):
                clock.now = due + worker.PERIOD_NS

            with patch.object(worker, "open_bus", return_value=bus), \
                    patch.object(worker, "sleep_until", side_effect=delayed_sleep), \
                    patch.object(worker.time, "monotonic_ns", side_effect=clock.monotonic_ns):
                with self.assertRaises(worker.InputFailure):
                    worker.sender("vcan0", output, TOKEN, worker.StopSignals())
            self.assertEqual(bus.sent, [])
            self.assertEqual(read_events(output, "input_events.jsonl")[0]["event"], "missed_slot")

    def test_sender_preparation_deadline_and_partial_send_are_failures(self):
        for partial in (False, True):
            with self.subTest(partial=partial), tempfile.TemporaryDirectory() as directory:
                output, clock, bus = Path(directory), FakeClock(), FakeBus()
                if partial:
                    bus.send = lambda _raw: 15

                def first_sleep(due, _signals, _watchdog):
                    clock.now = due if partial else 1_000_000_000 + worker.PREPARE_NS

                with patch.object(worker, "open_bus", return_value=bus), \
                        patch.object(worker, "sleep_until", side_effect=first_sleep), \
                        patch.object(worker.time, "monotonic_ns", side_effect=clock.monotonic_ns):
                    with self.assertRaises(worker.InputFailure if partial else OSError):
                        worker.sender("vcan0", output, TOKEN, worker.StopSignals())
                if partial:
                    self.assertEqual(read_events(output, "input_events.jsonl")[0]["bytes_sent"], 15)


class ObserverTests(unittest.TestCase):
    def test_observer_drains_all_queued_frames_after_sigterm(self):
        with tempfile.TemporaryDirectory() as directory:
            output, signals = Path(directory), worker.StopSignals()
            packets = [worker.fixture_frames(TOKEN, slot)[0] for slot in range(3)]
            bus = FakeBus(packets, lambda: signals.handler(signal.SIGTERM, None))
            with patch.object(worker, "open_bus", return_value=bus):
                result = worker.observer("vcan0", output, TOKEN, signals)
            self.assertEqual(result["received_frames"], 3)
            self.assertEqual(result["drained_after_sigterm_frames"], 2)
            self.assertEqual(bus.timeout, 0.0)
            self.assertEqual([event["raw_frame_hex"] for event in read_events(output, "can_observer.jsonl")],
                             [raw.hex() for raw in packets])

    def test_observer_preserves_foreign_token_and_malformed_raw_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            output, signals = Path(directory), worker.StopSignals()
            foreign = struct.pack("=IB3x8s", 0x100, 8, bytes.fromhex("e803000100000000"))
            bus = FakeBus((foreign, b"bad"))
            received = 0

            def terminate():
                nonlocal received
                received += 1
                if received == 3:
                    signals.handler(signal.SIGTERM, None)

            bus.on_receive = terminate
            with patch.object(worker, "open_bus", return_value=bus):
                result = worker.observer("vcan0", output, TOKEN, signals)
            events = read_events(output, "can_observer.jsonl")
            self.assertEqual(events[0]["raw_frame_hex"], foreign.hex())
            self.assertEqual(events[1]["raw_frame_hex"], b"bad".hex())
            self.assertIn("decode_error", events[1])
            self.assertEqual(result["decode_errors"], 1)
            self.assertEqual(result["termination"], "COORDINATOR_SIGTERM")
            self.assertEqual(bus.filters[0][2], b"".join(struct.pack("=II", item, 0x7FF)
                                                       for item in (0x100, 0x101, 0x200)))

    def test_observer_sigint_and_watchdog_are_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(worker, "open_bus", return_value=FakeBus()):
                with self.assertRaises(KeyboardInterrupt):
                    worker.observer("vcan0", Path(directory), TOKEN,
                                    worker.StopSignals(interrupt_requested=True))
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(worker, "open_bus", return_value=FakeBus()), \
                    patch.object(worker.time, "monotonic_ns", side_effect=(1, 65_000_000_001)):
                with self.assertRaises(OSError):
                    worker.observer("vcan0", Path(directory), TOKEN, worker.StopSignals())


class ControllerTests(unittest.TestCase):
    def test_heartbeat_does_not_delay_timeout_and_restoration_does_not_unlatch(self):
        with tempfile.TemporaryDirectory() as directory:
            output, clock, signals = Path(directory), FakeClock(), worker.StopSignals()
            origin = clock.now
            scheduled = [(origin + (20 + slot * 50) * 1_000_000,
                          worker.fixture_frames(TOKEN, slot)[0]) for slot in range(5)]
            scheduled += [(origin + moment * 1_000_000, worker.fixture_frames(TOKEN, 5)[1])
                          for moment in (270, 320, 370, 420, 470, 520)]
            scheduled += [(origin + 600_000_000, worker.fixture_frames(TOKEN, 160)[0])]

            class ScheduledBus(FakeBus):
                """관측 시각이 된 프레임만 반환해 실제 대기 없이 중단을 재현한다."""

                def recv(self, _size):
                    clock.advance(worker.POLL_NS)
                    if (output / "controller_input_ready.json").exists() and not (output / "controller_arm.json").exists():
                        worker.write_json(output / "controller_arm.json", {
                            "run_token": TOKEN, "host_monotonic_ns": clock.monotonic_ns(),
                        })
                    if clock.now >= origin + 650_000_000:
                        signals.handler(signal.SIGTERM, None)
                    if scheduled and clock.now >= scheduled[0][0]:
                        return scheduled.pop(0)[1]
                    raise socket.timeout()

            bus = ScheduledBus()
            with patch.object(worker, "open_bus", return_value=bus), \
                    patch.object(worker.time, "monotonic_ns", side_effect=clock.monotonic_ns):
                result = worker.controller("vcan0", output, TOKEN, signals)
            events = read_events(output, "sut_events.jsonl")
            requests = [event for event in events if event["event"] == "request_tx"]
            first_stop = next(event for event in requests if bytes.fromhex(event["data_hex"])[1] == 2)
            initial_normal = [event for event in events if event["event"] == "rx"
                              and event.get("accepted") and event["counter"] < 5]
            last_rx = initial_normal[-1]["host_monotonic_ns"]
            self.assertGreaterEqual(first_stop["s_begin_ns"] - last_rx, 200_000_000)
            self.assertLess(first_stop["s_begin_ns"] - last_rx, 200_000_000 + worker.POLL_NS + 100_000)
            self.assertEqual(result["snapshot"]["state"], "STOP_LATCHED")
            self.assertEqual(result["snapshot"]["reason"], 2)
            self.assertEqual(result["snapshot"]["last_counter"], 160)
            self.assertTrue(any(event.get("action") == "IGNORE_BACKGROUND" for event in events))
            self.assertTrue(all(bytes.fromhex(event["data_hex"])[0:2] == b"\1\2"
                                for event in requests if event["s_begin_ns"] >= first_stop["s_begin_ns"]))
            self.assertEqual([bytes.fromhex(event["data_hex"])[2] for event in requests],
                             list(range(len(requests))))

    def test_arm_ack_follows_normal_tx_and_init_never_returns(self):
        with tempfile.TemporaryDirectory() as directory:
            output, clock, signals = Path(directory), FakeClock(), worker.StopSignals()
            packets = [worker.fixture_frames(TOKEN, slot)[0] for slot in range(5)]
            bus = FakeBus(packets)

            def coordinate():
                clock.advance(worker.POLL_NS)
                if (output / "controller_armed.json").exists():
                    self.assertEqual(worker.CAN_FRAME.unpack(bus.sent[-1])[2][0:2], b"\0\0")
                    signals.handler(signal.SIGTERM, None)
                elif (output / "controller_input_ready.json").exists() and not (output / "controller_arm.json").exists():
                    worker.write_json(output / "controller_arm.json", {
                        "run_token": TOKEN, "host_monotonic_ns": clock.monotonic_ns(),
                    })

            bus.on_receive = coordinate
            with patch.object(worker, "open_bus", return_value=bus), \
                    patch.object(worker.time, "monotonic_ns", side_effect=clock.monotonic_ns):
                result = worker.controller("vcan0", output, TOKEN, signals)
            events = read_events(output, "sut_events.jsonl")
            sent = [event for event in events if event["event"] == "request_tx"]
            decoded = [worker.CAN_FRAME.unpack(raw)[2] for raw in bus.sent]
            self.assertEqual(decoded[0][0:2], b"\1\4")
            normal = next(index for index, payload in enumerate(decoded) if payload[0] == 0)
            self.assertTrue(all(payload[0:2] == b"\0\0" for payload in decoded[normal:]))
            self.assertEqual([payload[2] for payload in decoded], list(range(len(decoded))))
            ack = json.loads((output / "controller_armed.json").read_text())
            self.assertLessEqual(ack["host_monotonic_ns"], sent[normal]["s_begin_ns"])
            self.assertGreaterEqual(ack["acknowledged_monotonic_ns"], sent[normal]["s_done_ns"])
            self.assertEqual(result["snapshot"]["state"], "ARMED")
            self.assertEqual(result["termination"], "COORDINATOR_SIGTERM")
            self.assertEqual(bus.timeout, 0.01)
            self.assertTrue(all(event["bytes_sent"] == 16 for event in sent))

    def test_controller_refuses_arm_before_input_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            output, clock = Path(directory), FakeClock()
            worker.write_json(output / "controller_arm.json", {"run_token": TOKEN, "host_monotonic_ns": clock.now})
            with patch.object(worker, "open_bus", return_value=FakeBus()), \
                    patch.object(worker.time, "monotonic_ns", side_effect=clock.monotonic_ns):
                with self.assertRaises(worker.InputFailure):
                    worker.controller("vcan0", output, TOKEN, worker.StopSignals())
            self.assertFalse((output / "controller_armed.json").exists())

    def test_controller_rejects_arm_older_than_input_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            output, clock = Path(directory), FakeClock()
            started = clock.now
            packets = [worker.fixture_frames(TOKEN, slot)[0] for slot in range(5)]

            def stale_arm():
                clock.advance(worker.POLL_NS)
                if (output / "controller_input_ready.json").exists() and not (output / "controller_arm.json").exists():
                    worker.write_json(output / "controller_arm.json", {
                        "run_token": TOKEN, "host_monotonic_ns": started,
                    })

            with patch.object(worker, "open_bus", return_value=FakeBus(packets, stale_arm)), \
                    patch.object(worker.time, "monotonic_ns", side_effect=clock.monotonic_ns):
                with self.assertRaises(worker.InputFailure):
                    worker.controller("vcan0", output, TOKEN, worker.StopSignals())
            self.assertFalse((output / "controller_armed.json").exists())

    def test_controller_arm_deadline_is_finite(self):
        with tempfile.TemporaryDirectory() as directory:
            clock = FakeClock()
            calls = 0

            def expired_clock():
                nonlocal calls
                calls += 1
                return clock.monotonic_ns() if calls <= 3 else clock.now + worker.PREPARE_NS

            with patch.object(worker, "open_bus", return_value=FakeBus()), \
                    patch.object(worker.time, "monotonic_ns", side_effect=expired_clock):
                with self.assertRaises(OSError):
                    worker.controller("vcan0", Path(directory), TOKEN, worker.StopSignals())
            self.assertFalse((Path(directory) / "controller_armed.json").exists())


class WorkerGuardTests(unittest.TestCase):
    def test_core_oserror_is_sut_error_while_actual_socket_oserror_is_environment_error(self):
        from tools import g4_controller_core

        for core_error in (False, True):
            with self.subTest(core_error=core_error), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                args = SimpleNamespace(worker="controller", interface="vcan0", output_dir=output, run_token=TOKEN)
                with patch.object(worker, "inspect_link"), \
                        patch.object(worker, "open_bus", return_value=FakeBus()) as open_socket:
                    if core_error:
                        with patch.object(g4_controller_core.DistanceTimeoutController, "poll", side_effect=OSError("코어 내부 오류")):
                            self.assertEqual(worker.run_worker(args), 5)
                    else:
                        open_socket.side_effect = OSError("실제 소켓 오류")
                        self.assertEqual(worker.run_worker(args), 2)
                result = json.loads((output / "controller_result.json").read_text())
                self.assertEqual(result["status"], "SUT_ERROR" if core_error else "ENV_ERROR")
                self.assertIn("코어 내부 오류" if core_error else "실제 소켓 오류", result["error"])

    def test_controller_program_errors_are_sut_error_and_socket_errors_are_environment_errors(self):
        for error, status, code in ((RuntimeError("SUT 오류"), "SUT_ERROR", 5),
                                    (ValueError("코어 오류"), "SUT_ERROR", 5),
                                    (OSError("소켓 오류"), "ENV_ERROR", 2),
                                    (worker.InputFailure("오래된 명령"), "INPUT_ERROR", 4)):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                args = SimpleNamespace(worker="controller", interface="vcan0", output_dir=output, run_token=TOKEN)
                with patch.object(worker, "inspect_link"), patch.object(worker, "controller", side_effect=error):
                    self.assertEqual(worker.run_worker(args), code)
                self.assertEqual(json.loads((output / "controller_result.json").read_text())["status"], status)

    def test_each_worker_refuses_physical_can_before_socket(self):
        for role in ("sender", "observer", "controller"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                args = SimpleNamespace(worker=role, interface="can0", output_dir=output, run_token=TOKEN)
                link = [{"ifname": "can0", "flags": ["UP"], "linkinfo": {"info_kind": "can"}}]
                response = SimpleNamespace(returncode=0, stdout=json.dumps(link), stderr="")
                with patch.object(worker.inspect_link.__globals__["subprocess"], "run", return_value=response), \
                        patch.object(worker, "open_bus") as open_socket:
                    self.assertEqual(worker.run_worker(args), 2)
                    open_socket.assert_not_called()
                result = json.loads((output / f"{role}_result.json").read_text())
                self.assertEqual(result["status"], "ENV_ERROR")
                self.assertEqual(result["role"], role)
                self.assertEqual(result["exit_code"], 2)
                self.assertTrue((output / f"{role}_preflight.json").exists())

    def test_existing_owned_evidence_is_preserved_for_all_roles(self):
        for role, name in (("sender", "trial_started.json"), ("observer", "can_observer.jsonl"),
                           ("controller", "controller_armed.json")):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                marker = output / name
                marker.write_text("preserve")
                args = SimpleNamespace(worker=role, interface="vcan0", output_dir=output, run_token=TOKEN)
                with patch.object(worker, "open_bus") as open_socket, self.assertRaises(FileExistsError):
                    worker.run_worker(args)
                open_socket.assert_not_called()
                self.assertEqual(marker.read_text(), "preserve")

    def test_error_classes_signal_metadata_and_handlers_are_preserved(self):
        cases = ((worker.InputFailure("슬롯 누락"), "INPUT_ERROR", 4),
                 (RuntimeError("내부 오류"), "TOOL_ERROR", 3),
                 (OSError("장치 오류"), "ENV_ERROR", 2),
                 (subprocess.TimeoutExpired("ip", 5), "ENV_ERROR", 2),
                 (KeyboardInterrupt("취소"), "INTERRUPTED", 130))
        for error, status, code in cases:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                args = SimpleNamespace(worker="sender", interface="vcan0", output_dir=output, run_token=TOKEN)
                before = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
                with patch.object(worker, "inspect_link"), patch.object(worker, "sender", side_effect=error):
                    self.assertEqual(worker.run_worker(args), code)
                self.assertEqual({sig: signal.getsignal(sig) for sig in before}, before)
                result = json.loads((output / "sender_result.json").read_text())
                self.assertEqual(result["status"], status)
                self.assertEqual(result["exit_code"], code)
                self.assertGreaterEqual(result["done_monotonic_ns"], result["begin_monotonic_ns"])
                self.assertTrue((output / "sender_error.txt").exists())

    def test_sigterm_is_sender_cancel_and_observer_controller_normal_stop(self):
        signals = worker.StopSignals()
        signals.handler(signal.SIGTERM, None)
        with self.assertRaises(KeyboardInterrupt):
            worker.sleep_until(0, signals, worker.WATCHDOG_NS)
        for role in ("observer", "controller"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as directory:
                with patch.object(worker, "open_bus", return_value=FakeBus()):
                    result = getattr(worker, role)("vcan0", Path(directory), TOKEN, signals)
                self.assertEqual(result["termination"], "COORDINATOR_SIGTERM")
        for role in ("sender", "observer", "controller"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as directory:
                with patch.object(worker, "open_bus", return_value=FakeBus()), self.assertRaises(KeyboardInterrupt):
                    getattr(worker, role)("vcan0", Path(directory), TOKEN,
                                          worker.StopSignals(interrupt_requested=True))

    def test_isolated_cli_help_and_invalid_uint32(self):
        source = str(Path(worker.__file__).resolve())
        result = subprocess.run([sys.executable, "-I", source, "--help"],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("controller", result.stdout)
        result = subprocess.run([sys.executable, "-I", source, "--worker", "sender", "--output-dir", "/tmp",
                                 "--run-token", "4294967296"], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn("uint32", result.stderr)


if __name__ == "__main__":
    unittest.main()
