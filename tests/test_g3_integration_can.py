"""G3 독립 worker의 단위 검사다. 실제 CAN/CARLA 실행 근거가 아니다."""

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

from tools import g3_integration_can as worker


TOKEN = 0x12345678


class FakeBus:
    """송수신 원시 바이트만 보존하며 실제 socket을 만들지 않는다."""

    def __init__(self, packets=(), on_receive=None):
        self.sent, self.filters = [], []
        self.packets = iter(packets)
        self.on_receive = on_receive

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def send(self, raw):
        self.sent.append(raw)
        return 16

    def setsockopt(self, *values):
        self.filters.append(values)

    def recv(self, _size):
        try:
            return next(self.packets)
        except StopIteration:
            if self.on_receive:
                self.on_receive()
            raise socket.timeout()


class FixtureTests(unittest.TestCase):
    def test_known_normal_stop_and_restoration_bytes(self):
        fixture = worker.fixture_payloads(TOKEN)
        self.assertEqual(len(fixture), 20)
        self.assertEqual(fixture[0].hex(), "0000000078563412")
        self.assertEqual(fixture[5].hex(), "0101050078563412")
        self.assertEqual(fixture[9].hex(), "0101090078563412")
        self.assertEqual(fixture[10].hex(), "00000a0078563412")
        self.assertEqual(fixture[19].hex(), "0000130078563412")
        self.assertEqual([p[2] for p in fixture], list(range(20)))
        self.assertTrue(all(p[3] == 0 for p in fixture))

    def test_uint32_token_boundaries(self):
        for token in (0, 0xFFFFFFFF):
            self.assertTrue(all(p[4:] == token.to_bytes(4, "little")
                                for p in worker.fixture_payloads(token)))
        for token in (-1, 0x100000000, True):
            with self.assertRaises(ValueError):
                worker.fixture_payloads(token)


class SenderTests(unittest.TestCase):
    def test_sender_records_actual_call_boundaries_and_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "sender_start.json").write_text("{}")
            bus = FakeBus()
            times = iter((1_000_000_000, 1_000_000_001, 1_000_000_002,
                          *(value for i in range(20) for value in
                            (1_100_000_002 + i * worker.PERIOD_NS + 10,
                             1_100_000_002 + i * worker.PERIOD_NS + 20))))
            with patch.object(worker, "open_bus", return_value=bus), \
                    patch.object(worker, "sleep_until"), \
                    patch.object(worker.time, "monotonic_ns", side_effect=lambda: next(times)):
                result = worker.sender("vcan0", output, TOKEN, worker.StopSignals())
            events = [json.loads(line) for line in (output / "input_events.jsonl").read_text().splitlines()]
            self.assertEqual(result["sent_frames"], 20)
            self.assertEqual(len(bus.sent), 20)
            self.assertTrue((output / "sender_ready.json").exists())
            for i, event in enumerate(events):
                expected = bytes([int(5 <= i < 10), int(5 <= i < 10), i, 0, 0x78, 0x56, 0x34, 0x12])
                self.assertEqual(bus.sent[i], struct.pack("=IB3x8s", 0x200, 8, expected))
                self.assertEqual(event["slot"], i)
                self.assertLessEqual(event["scheduled_ns"], event["s_begin_ns"])
                self.assertLessEqual(event["s_begin_ns"], event["s_done_ns"])

    def test_late_slot_never_sends_catchup_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "sender_start.json").write_text("{}")
            bus = FakeBus()
            with patch.object(worker, "open_bus", return_value=bus), \
                    patch.object(worker, "sleep_until"), \
                    patch.object(worker.time, "monotonic_ns", side_effect=(1, 2, 3, 150_000_003)):
                with self.assertRaises(worker.InputFailure):
                    worker.sender("vcan0", output, TOKEN, worker.StopSignals())
            self.assertEqual(bus.sent, [])
            self.assertIn("missed_slot", (output / "input_events.jsonl").read_text())

    def test_start_wait_deadline_is_not_unbounded(self):
        with tempfile.TemporaryDirectory() as directory:
            bus = FakeBus()
            with patch.object(worker, "open_bus", return_value=bus), \
                    patch.object(worker.time, "monotonic_ns", side_effect=(1, 35_000_000_001)):
                with self.assertRaises(OSError):
                    worker.sender("vcan0", Path(directory), TOKEN, worker.StopSignals())
            self.assertEqual(bus.sent, [])

    def test_sender_stop_is_interrupted_not_complete(self):
        signals = worker.StopSignals(terminate_requested=True)
        with self.assertRaises(KeyboardInterrupt):
            worker.sleep_until(100, signals, 1000)

    def test_partial_write_preserves_actual_count_and_stops_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "sender_start.json").write_text("{}")
            bus = FakeBus()
            bus.send = lambda _raw: 15
            with patch.object(worker, "open_bus", return_value=bus), \
                    patch.object(worker, "sleep_until"), \
                    patch.object(worker.time, "monotonic_ns", side_effect=(1, 2, 3, 100_000_004, 100_000_005)):
                with self.assertRaises(worker.InputFailure):
                    worker.sender("vcan0", output, TOKEN, worker.StopSignals())
            events = [json.loads(line) for line in (output / "input_events.jsonl").read_text().splitlines()]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["bytes_sent"], 15)


class ObserverTests(unittest.TestCase):
    def test_foreign_token_and_malformed_bytes_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            signals = worker.StopSignals()
            foreign = struct.pack("=IB3x8s", 0x200, 8, bytes.fromhex("0101000011223344"))
            bus = FakeBus((foreign, b"bad"), lambda: signals.handler(signal.SIGTERM, None))
            with patch.object(worker, "open_bus", return_value=bus):
                result = worker.observer("vcan0", output, signals)
            events = [json.loads(line) for line in (output / "can_observer.jsonl").read_text().splitlines()]
            self.assertEqual(result["received_frames"], 2)
            self.assertEqual(result["decode_errors"], 1)
            self.assertEqual(events[0]["raw_frame_hex"], foreign.hex())
            self.assertEqual(events[1]["raw_frame_hex"], b"bad".hex())
            self.assertIn("decode_error", events[1])
            self.assertEqual(bus.filters, [(socket.SOL_CAN_RAW, socket.CAN_RAW_FILTER,
                                           struct.pack("=II", 0x200, 0x7FF))])
            self.assertEqual(result["termination"], "COORDINATOR_SIGTERM")

    def test_observer_watchdog_and_interrupt_are_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(worker, "open_bus", return_value=FakeBus()), \
                    patch.object(worker.time, "monotonic_ns", side_effect=(1, 45_000_000_001)):
                with self.assertRaises(OSError):
                    worker.observer("vcan0", Path(directory), worker.StopSignals())
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(worker, "open_bus", return_value=FakeBus()):
                with self.assertRaises(KeyboardInterrupt):
                    worker.observer("vcan0", Path(directory), worker.StopSignals(interrupt_requested=True))


class WorkerGuardTests(unittest.TestCase):
    def test_direct_worker_refuses_physical_can_before_opening_socket(self):
        for role in ("sender", "observer"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as directory:
                args = SimpleNamespace(worker=role, interface="can0", output_dir=Path(directory), run_token=TOKEN)
                link = [{"ifname": "can0", "flags": ["UP"], "linkinfo": {"info_kind": "can"}}]
                result = SimpleNamespace(returncode=0, stdout=json.dumps(link), stderr="")
                with patch.object(worker.inspect_link.__globals__["subprocess"], "run", return_value=result), \
                        patch.object(worker, "open_bus") as open_socket:
                    self.assertEqual(worker.run_worker(args), 2)
                    open_socket.assert_not_called()
                self.assertTrue((Path(directory) / f"{role}_preflight.json").exists())
                saved = json.loads((Path(directory) / f"{role}_result.json").read_text())
                self.assertEqual(saved["status"], "ENV_ERROR")

    def test_existing_owned_evidence_is_never_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            marker = output / "input_events.jsonl"
            marker.write_text("preserve")
            args = SimpleNamespace(worker="sender", interface="vcan0", output_dir=output, run_token=TOKEN)
            with patch.object(worker, "open_bus") as open_socket:
                with self.assertRaises(FileExistsError):
                    worker.run_worker(args)
                open_socket.assert_not_called()
            self.assertEqual(marker.read_text(), "preserve")

    def test_worker_error_classes_and_signal_handlers_are_preserved(self):
        for error, status, code in ((worker.InputFailure("슬롯 누락"), "INPUT_ERROR", 4),
                                    (RuntimeError("내부 오류"), "TOOL_ERROR", 3),
                                    (KeyboardInterrupt("취소"), "INTERRUPTED", 130)):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                args = SimpleNamespace(worker="sender", interface="vcan0", output_dir=output, run_token=TOKEN)
                before = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
                with patch.object(worker, "inspect_link"), \
                        patch.object(worker, "sender", side_effect=error):
                    self.assertEqual(worker.run_worker(args), code)
                self.assertEqual({sig: signal.getsignal(sig) for sig in before}, before)
                saved = json.loads((output / "sender_result.json").read_text())
                self.assertEqual(saved["status"], status)
                self.assertEqual(saved["exit_code"], code)
                self.assertGreaterEqual(saved["done_monotonic_ns"], saved["begin_monotonic_ns"])
                self.assertTrue((output / "sender_error.txt").exists())

    def test_isolated_cli_help_imports_only_own_repository(self):
        result = subprocess.run([sys.executable, "-I", str(Path(worker.__file__).resolve()), "--help"],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--worker", result.stdout)


if __name__ == "__main__":
    unittest.main()
