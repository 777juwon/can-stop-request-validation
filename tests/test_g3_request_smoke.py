"""요청 바이트와 관측 판정의 단위 검사다. 실제 vCAN/CARLA 실행과 구분한다."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import g3_request_smoke as g3


TOKEN = 0x12345678


def fixture():
    """도구의 encoder를 사용하지 않고 고정 계약으로 원시 관측을 만든다."""
    tx, rx = [], []
    for i in range(10):
        stop = int(i >= 5)
        payload = bytes([stop, stop, i, 0, 0x78, 0x56, 0x34, 0x12])
        raw = bytes.fromhex("0002000008000000") + payload
        frame = {"arbitration_id": 0x200, "dlc": 8, "extended": False,
                 "remote": False, "error_frame": False,
                 "data_hex": payload.hex(), "raw_frame_hex": raw.hex()}
        due = 1_100_000_000 + i * 50_000_000
        tx.append({**frame, "event": "tx", "pid": 11, "slot": i,
                   "scheduled_ns": due, "s_begin_ns": due + 10,
                   "s_done_ns": due + 100, "bytes_sent": 16})
        # 실제 수신은 송신 호출의 성공 반환보다 먼저 관측될 수 있다.
        rx.append({**frame, "event": "rx", "pid": 12,
                   "host_monotonic_ns": due + 20,
                   "fields": {"stop": stop, "reason": stop, "counter": i,
                              "reserved": 0, "run_token": TOKEN}})
    return tx, rx


def verdict(tx, rx, token=TOKEN):
    return g3.evaluate(tx, rx, token, ready_ns=1_000_000_000, ended_ns=2_000_000_000)


class RequestBytesTests(unittest.TestCase):
    def test_known_bytes_and_little_endian_token(self):
        payload = g3.encode_request(1, 1, 0xAB, TOKEN)
        self.assertEqual(payload.hex(), "0101ab0078563412")
        self.assertEqual(g3.CAN_FRAME.pack(g3.STOP_ID, 8, payload).hex(),
                         "00020000080000000101ab0078563412")
        self.assertEqual(g3.decode_request(payload),
                         {"stop": 1, "reason": 1, "counter": 0xAB,
                          "reserved": 0, "run_token": TOKEN})

    def test_all_defined_reasons_and_unsigned_boundaries(self):
        for reason in range(5):
            for counter, token in ((0, 0), (255, 0xFFFFFFFF)):
                decoded = g3.decode_request(g3.encode_request(1, reason, counter, token))
                self.assertEqual((decoded["reason"], decoded["counter"], decoded["run_token"]),
                                 (reason, counter, token))
                self.assertEqual(decoded["reserved"], 0)

    def test_noninteger_and_out_of_range_encoding_rejected(self):
        for field in range(4):
            maximum = 0xFFFFFFFF if field == 3 else 255
            for bad in (-1, maximum + 1, True, 1.0, "1", None):
                values = [1, 1, 0, TOKEN]
                values[field] = bad
                with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                    g3.encode_request(*values)

    def test_payload_length_is_exactly_eight(self):
        for size in (0, 7, 9, 64):
            with self.subTest(size=size), self.assertRaises(ValueError):
                g3.decode_request(bytes(size))

    def test_unassigned_fields_are_preserved_without_adapter_policy(self):
        decoded = g3.decode_request(bytes.fromhex("fffeff7e78563412"))
        self.assertEqual(decoded, {"stop": 255, "reason": 254, "counter": 255,
                                  "reserved": 126, "run_token": TOKEN})

    def test_nonclassic_length_and_invalid_dlc_rejected(self):
        for raw in (bytes(15), bytes(72), bytes.fromhex("0002000009000000") + bytes(8)):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                g3.frame_fields(raw)


class RequestObservationTests(unittest.TestCase):
    def test_exact_raw_observations_pass_only_transport(self):
        tx, rx = fixture()
        result = verdict(tx, rx)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["full_g3_verified"])
        self.assertFalse(result["carla_executed"])
        self.assertEqual(result["main_trials_executed"], 0)

    def test_send_success_without_observation_is_not_pass(self):
        tx, _ = fixture()
        self.assertEqual(verdict(tx, [])["status"], "FAIL")

    def test_missing_duplicate_or_reordered_frames_fail(self):
        tx, rx = fixture()
        for damaged in (rx[:-1], rx + [rx[-1]], [rx[1], rx[0], *rx[2:]]):
            with self.subTest(count=len(damaged)):
                self.assertEqual(verdict(tx, damaged)["status"], "FAIL")

    def test_raw_bytes_cannot_disagree_with_logged_payload(self):
        tx, rx = fixture()
        rx[5]["raw_frame_hex"] = rx[5]["raw_frame_hex"][:-2] + "99"
        self.assertEqual(verdict(tx, rx)["status"], "FAIL")

    def test_decoded_fields_cannot_disagree_with_raw_bytes(self):
        tx, rx = fixture()
        rx[5]["fields"]["stop"] = 0
        self.assertEqual(verdict(tx, rx)["status"], "FAIL")

    def test_foreign_token_is_not_the_expected_fixture(self):
        tx, rx = fixture()
        self.assertEqual(verdict(tx, rx, TOKEN + 1)["status"], "FAIL")

    def test_flags_wrong_id_and_short_payload_fail(self):
        for can_id, dlc in ((0x80000200, 8), (0x40000200, 8),
                            (0x20000200, 8), (0x201, 8), (0x200, 7)):
            tx, rx = fixture()
            payload = bytes.fromhex(rx[5]["data_hex"])
            raw = g3.CAN_FRAME.pack(can_id, dlc, payload)
            rx[5].update(g3.frame_fields(raw))
            with self.subTest(can_id=can_id, dlc=dlc):
                self.assertEqual(verdict(tx, rx)["status"], "FAIL")

    def test_receive_before_send_begin_or_after_record_end_fails(self):
        for stamp in (999_999_999, 2_000_000_001):
            tx, rx = fixture()
            rx[0]["host_monotonic_ns"] = stamp
            self.assertEqual(verdict(tx, rx)["status"], "FAIL")

    def test_slot_schedule_and_late_sender_fail(self):
        tx, rx = fixture()
        tx[4]["scheduled_ns"] -= 1
        self.assertEqual(verdict(tx, rx)["status"], "FAIL")
        tx, rx = fixture()
        tx[-1]["s_begin_ns"] = tx[-1]["scheduled_ns"] + g3.PERIOD_NS
        tx[-1]["s_done_ns"] = tx[-1]["s_begin_ns"] + 100
        rx[-1]["host_monotonic_ns"] = tx[-1]["s_begin_ns"] + 50
        self.assertEqual(verdict(tx, rx)["status"], "FAIL")

    def test_receive_timestamp_order_is_checked(self):
        tx, rx = fixture()
        rx[0]["host_monotonic_ns"] = rx[-1]["host_monotonic_ns"]
        self.assertEqual(verdict(tx, rx)["status"], "FAIL")

    def test_optimized_python_keeps_raw_flag_checks(self):
        tx, rx = fixture()
        raw = g3.CAN_FRAME.pack(0x80000200, 8, bytes.fromhex(rx[5]["data_hex"]))
        rx[5].update(g3.frame_fields(raw))
        code = """
import importlib.util,json,sys
spec=importlib.util.spec_from_file_location('g3_check',sys.argv[1])
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
data=json.load(sys.stdin)
result=module.evaluate(data['tx'],data['rx'],data['token'],1000000000,2000000000)
if result['status']!='FAIL':
    raise SystemExit(1)
"""
        result = subprocess.run([sys.executable, "-I", "-O", "-c", code, str(Path(g3.__file__).resolve())],
                                input=json.dumps({"tx": tx, "rx": rx, "token": TOKEN}),
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)


class RequestRuntimeGuardsTests(unittest.TestCase):
    def test_physical_down_and_ambiguous_interfaces_refused(self):
        link = {"ifname": "vcan0", "flags": ["UP"], "linkinfo": {"info_kind": "vcan"}}
        self.assertEqual(g3.validate_link([link], "vcan0"), link)
        physical = copy.deepcopy(link)
        physical["linkinfo"]["info_kind"] = "can"
        down = copy.deepcopy(link)
        down["flags"] = []
        for links in ([], [link, link], [physical], [down]):
            with self.subTest(links=links), self.assertRaises(OSError):
                g3.validate_link(links, "vcan0")

    def test_existing_directory_is_not_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(output_dir=Path(directory), interface="vcan0")
            with self.assertRaises(FileExistsError):
                g3.coordinate(args)

    def test_missing_interface_records_env_error_without_starting_workers(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new-run"
            args = SimpleNamespace(output_dir=output, interface="vcan0")
            with patch.object(g3, "inspect_link", side_effect=OSError("vcan0 없음")), \
                    patch.object(g3.subprocess, "run", return_value=SimpleNamespace(stdout="testcommit\n")), \
                    patch("builtins.print"), \
                    patch.object(g3.subprocess, "Popen") as start:
                self.assertEqual(g3.coordinate(args), 2)
                start.assert_not_called()
            result = json.loads((output / "verdict.json").read_text())
            self.assertEqual(result["status"], "ENV_ERROR")
            self.assertFalse(result["full_g3_verified"])
            self.assertEqual(json.loads((output / "commands.json").read_text()), [])

    def test_direct_worker_cannot_bypass_physical_interface_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            args = SimpleNamespace(output_dir=output, interface="can0", worker="sender", run_token=TOKEN)
            link = [{"ifname": "can0", "flags": ["UP"], "linkinfo": {"info_kind": "can"}}]
            result = SimpleNamespace(returncode=0, stdout=json.dumps(link), stderr="")
            with patch.object(g3.subprocess, "run", return_value=result), \
                    patch.object(g3.socket, "socket") as open_socket:
                self.assertEqual(g3.run_worker(args), 2)
                open_socket.assert_not_called()
            self.assertTrue((output / "sender_preflight.json").exists())
            self.assertEqual(json.loads((output / "sender_result.json").read_text())["status"], "ENV_ERROR")

    def test_receiver_early_exit_keeps_recorded_failure_classification(self):
        for status in ("TOOL_ERROR", "INPUT_ERROR", "ENV_ERROR"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "new-run"
                args = SimpleNamespace(output_dir=output, interface="vcan0")
                code = g3.EXIT_CODES[status]
                child = SimpleNamespace(pid=41, returncode=code, poll=lambda: code)

                def start(*_args, **_kwargs):
                    g3.write_json(output / "receiver_result.json", {"pid": 41, "role": "receiver",
                                                                   "status": status, "error": "의도한 실패"})
                    return child

                with patch.object(g3, "inspect_link", return_value={"ifname": "vcan0"}), \
                        patch.object(g3.subprocess, "run", return_value=SimpleNamespace(stdout="testcommit\n")), \
                        patch.object(g3.subprocess, "Popen", side_effect=start) as popen, \
                        patch("builtins.print"):
                    self.assertEqual(g3.coordinate(args), code)
                    self.assertEqual(popen.call_count, 1)
                self.assertEqual(json.loads((output / "verdict.json").read_text())["status"], status)

    def test_early_exit_cannot_inherit_pass_or_missing_result(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            self.assertEqual(g3.early_worker_failure(output, "receiver", 0).status, "TOOL_ERROR")
            g3.write_json(output / "receiver_result.json", {"status": "PASS"})
            self.assertEqual(g3.early_worker_failure(output, "receiver", 0).status, "TOOL_ERROR")


if __name__ == "__main__":
    unittest.main()
