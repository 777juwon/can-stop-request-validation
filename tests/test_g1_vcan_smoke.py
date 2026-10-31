"""Unit evidence only: these checks do not run vCAN or prove the G1 gate."""

import copy
import json
from pathlib import Path
import select
import signal
import struct
import subprocess
import sys
import tempfile
import textwrap
import unittest

from tools import g1_vcan_smoke as smoke


TOKEN = 0x11223344
START_NS = 1_000_000_000


def observed_fixture():
    tx = [{"event": "fixture_start", "start_ns": START_NS}]
    rx = []
    for frame in smoke.fixture_frames(TOKEN):
        slot = frame["slot"]
        due = START_NS + slot * smoke.PERIOD_NS
        offset = 20_000 if frame["arbitration_id"] == smoke.BACKGROUND_ID else 0
        raw = smoke.pack_frame(frame["arbitration_id"], bytes.fromhex(frame["data_hex"]))
        decoded = smoke.unpack_frame(raw)
        tx.append({"event": "tx", "slot": slot, "scheduled_ns": due,
                   "s_begin_ns": due + offset, "s_done_ns": due + offset + 1_000,
                   "bytes_sent": 16, **decoded})
        rx.append({"event": "rx", "host_monotonic_ns": due + offset + 2_000, **decoded})
    tx.append({"event": "target_stopped", "slot": 20})
    tx.append({"event": "fixture_end"})
    return tx, rx


class FrameTests(unittest.TestCase):
    def test_known_classic_can_bytes(self):
        raw = smoke.pack_frame(0x100, bytes.fromhex("e803070144332211"))
        self.assertEqual(raw, struct.pack("=I", 0x100) + bytes.fromhex("08000000e803070144332211"))
        decoded = smoke.unpack_frame(raw)
        self.assertEqual((decoded["arbitration_id"], decoded["dlc"], decoded["data_hex"]),
                         (0x100, 8, "e803070144332211"))
        self.assertFalse(decoded["is_extended_id"])

    def test_rejects_non_classic_length_or_id(self):
        for can_id, data in ((0x800, b""), (-1, b""), (0x100, b"123456789")):
            with self.subTest(can_id=can_id, data=data), self.assertRaises(ValueError):
                smoke.pack_frame(can_id, data)
        for raw in (b"\0" * 15, struct.pack("=IB3x8s", 0x100, 9, b"\0" * 8)):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                smoke.unpack_frame(raw)

    def test_fixture_known_bytes_and_counts(self):
        fixture = smoke.fixture_frames(TOKEN)
        self.assertEqual(len(fixture), 60)
        self.assertEqual(fixture[0]["data_hex"], "e803000144332211")
        self.assertEqual(fixture[1]["data_hex"], "0000000044332211")
        self.assertEqual(fixture[-1]["data_hex"], "2700000044332211")
        self.assertTrue(all(frame["arbitration_id"] == 0x101 for frame in fixture if frame["slot"] >= 20))


class OracleTests(unittest.TestCase):
    def verdict(self, tx, rx):
        return smoke.evaluate_observations(tx, rx, TOKEN)

    def test_complete_observations_pass_only_connection_fixture(self):
        verdict = self.verdict(*observed_fixture())
        self.assertEqual(verdict["status"], "PASS")
        self.assertEqual(verdict["main_comparison_runs_executed"], 0)
        self.assertEqual(verdict["G2"], "NOT_RUN")
        self.assertEqual(verdict["sender_background_intervals"]["min_ns"], 50_000_000)

    def test_sender_success_without_observer_cannot_pass(self):
        tx, _ = observed_fixture()
        verdict = self.verdict(tx, [])
        self.assertEqual(verdict["status"], "FAIL")
        self.assertIn("observer_frame_mismatch", [item["code"] for item in verdict["failures"]])

    def test_missing_or_duplicate_observation_fails(self):
        tx, rx = observed_fixture()
        for altered in (rx[:-1], rx + [rx[-1]]):
            with self.subTest(count=len(altered)):
                self.assertEqual(self.verdict(tx, altered)["status"], "FAIL")

    def test_wrong_bytes_or_dlc_cannot_pass_on_counts_alone(self):
        tx, rx = observed_fixture()
        for field, value in (("data_hex", "e903000144332211"), ("dlc", 7), ("is_extended_id", True)):
            altered = copy.deepcopy(rx)
            altered[0][field] = value
            with self.subTest(field=field):
                self.assertEqual(self.verdict(tx, altered)["status"], "FAIL")

    def test_target_must_not_follow_post_stop_background(self):
        tx, rx = observed_fixture()
        delayed_target = rx.pop(0)
        delayed_target["host_monotonic_ns"] = START_NS + 1_500_000_000
        rx.append(delayed_target)
        verdict = self.verdict(tx, rx)
        self.assertIn("target_observed_after_post_stop_heartbeat", [item["code"] for item in verdict["failures"]])

    def test_foreign_run_token_does_not_replace_missing_fixture(self):
        tx, rx = observed_fixture()
        altered = copy.deepcopy(rx)
        altered[-1]["data_hex"] = altered[-1]["data_hex"][:-8] + "88776655"
        verdict = self.verdict(tx, altered)
        self.assertEqual(verdict["status"], "FAIL")
        self.assertEqual(verdict["ignored_other_token_frames"], 1)

    def test_send_slot_upper_boundary_is_exclusive(self):
        tx, rx = observed_fixture()
        for offset, expected in ((49_999_999, "PASS"), (50_000_000, "FAIL"), (-1, "FAIL")):
            altered = copy.deepcopy(tx)
            last = next(item for item in reversed(altered) if item["event"] == "tx")
            last["s_begin_ns"] = last["scheduled_ns"] + offset
            last["s_done_ns"] = last["s_begin_ns"] + 1
            observed = copy.deepcopy(rx)
            observed[-1]["host_monotonic_ns"] = last["s_done_ns"] + 1
            with self.subTest(offset=offset):
                self.assertEqual(self.verdict(altered, observed)["status"], expected)

    def test_raw_frame_disagreement_and_impossible_observation_time_fail(self):
        tx, rx = observed_fixture()
        altered = copy.deepcopy(rx)
        altered[0]["raw_frame_hex"] = smoke.pack_frame(0x100, bytes.fromhex("e903000144332211")).hex()
        verdict = self.verdict(tx, altered)
        self.assertIn("raw_frame_fields_disagree", [item["code"] for item in verdict["failures"]])
        altered = copy.deepcopy(rx)
        altered[0]["host_monotonic_ns"] = START_NS - 1
        verdict = self.verdict(tx, altered)
        self.assertIn("observation_precedes_send_call", [item["code"] for item in verdict["failures"]])


class GuardTests(unittest.TestCase):
    def test_sigterm_preserves_interrupted_verdict_and_commands(self):
        # Real signal + real coordinator finalization, but no real interface or
        # CAN socket. These temporary unit artifacts cannot establish G1 PASS.
        harness = textwrap.dedent("""
            import importlib.util
            import sys
            import time
            from unittest.mock import patch

            spec = importlib.util.spec_from_file_location("g1_unit_target", sys.argv[1])
            smoke = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(smoke)

            def blocked_interface_check(interface, commands):
                commands.append({
                    "argv": ["UNIT_TEST_ONLY_MOCK_INTERFACE_WAIT"],
                    "unit_test_only": True,
                    "real_socketcan_executed": False,
                })
                print("UNIT_TEST_READY_FOR_SIGTERM", flush=True)
                while True:
                    time.sleep(0.05)

            with patch.object(smoke, "inspect_interface", blocked_interface_check):
                raise SystemExit(smoke.main([
                    "--interface", "vcan0", "--output-dir", sys.argv[2],
                ]))
        """)
        with tempfile.TemporaryDirectory(prefix="g1-sigterm-unit-", dir="/tmp") as tmp:
            output = Path(tmp) / "unit-evidence"
            process = subprocess.Popen(
                [sys.executable, "-I", "-c", harness, str(Path(smoke.__file__).resolve()), str(output)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            try:
                ready, _, _ = select.select([process.stdout], [], [], 5)
                self.assertTrue(ready, "isolated signal harness did not become ready")
                self.assertEqual(process.stdout.readline().strip(), "UNIT_TEST_READY_FOR_SIGTERM")
                process.send_signal(signal.SIGTERM)
                stdout, stderr = process.communicate(timeout=5)
                self.assertEqual(process.returncode, 130, stderr)
                self.assertEqual(stderr, "")
                self.assertEqual(json.loads(stdout)["status"], "INTERRUPTED")
                verdict = json.loads((output / "verdict.json").read_text())
                commands = json.loads((output / "commands.json").read_text())
                self.assertEqual(verdict["status"], "INTERRUPTED")
                self.assertEqual(verdict["main_comparison_runs_executed"], 0)
                self.assertGreaterEqual(verdict["done_ns"], verdict["begin_ns"])
                self.assertEqual(len(commands), 1)
                self.assertTrue(commands[0]["unit_test_only"])
                self.assertFalse(commands[0]["real_socketcan_executed"])
                self.assertFalse((output / "receiver.jsonl").exists())
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=5)

    def test_refuses_physical_or_down_interface(self):
        for kind, flags in (("can", ["UP"]), ("vcan", [])):
            links = [{"ifname": "vcan0", "linkinfo": {"info_kind": kind}, "flags": flags}]
            with self.subTest(kind=kind, flags=flags), self.assertRaises(OSError):
                smoke.validate_link_info(links, "vcan0")

    def test_output_directory_is_never_reused(self):
        with tempfile.TemporaryDirectory(prefix="g1-unit-", dir="/tmp") as tmp:
            output = Path(tmp) / "run"
            smoke.claim_output_directory(output)
            marker = output / "original.txt"
            marker.write_text("keep")
            with self.assertRaises(FileExistsError):
                smoke.claim_output_directory(output)
            self.assertEqual(marker.read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
