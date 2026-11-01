"""G4 실행기의 준비 경계와 실행 전 보호 장치를 검사한다."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import g4_carla_smoke as g4


class TrialBoundaryTests(unittest.TestCase):
    def samples(self):
        return [{"frame": 100 + i, "simulation_time_s": i * .05,
                 "host_monotonic_ns": i * 50_000_000, "speed_mps": 5 / 3.6}
                for i in range(21)]

    def test_tick_crossing_t0_is_preserved_but_not_used_as_ready(self):
        samples = self.samples()
        samples.append({"frame": 121, "simulation_time_s": 1.05,
                        "host_monotonic_ns": 1_050_000_000, "speed_mps": 0})
        ready = g4.select_trial_ready(samples, 1_020_000_000)
        self.assertEqual(ready["frame"], 120)

    def test_good_samples_after_t0_cannot_replace_missing_initial_motion(self):
        samples = self.samples()
        samples[0]["speed_mps"] = 0
        samples.append({"frame": 121, "simulation_time_s": 1.05,
                        "host_monotonic_ns": 1_050_000_000, "speed_mps": 5 / 3.6})
        with self.assertRaises(g4.RunError) as caught:
            g4.select_trial_ready(samples, 1_020_000_000)
        self.assertEqual(caught.exception.status, "ENV_ERROR")

    def test_missing_or_noncontiguous_initial_samples_cannot_be_ready(self):
        for change in ("count", "frame", "time"):
            samples = self.samples()
            if change == "count":
                samples.pop(0)
            elif change == "frame":
                samples[8]["frame"] += 1
            else:
                samples[8]["simulation_time_s"] += .01
            with self.subTest(change=change), self.assertRaises(g4.RunError):
                g4.select_trial_ready(samples, 1_020_000_000)


class RuntimeGuardTests(unittest.TestCase):
    def test_initial_request_cannot_precede_independent_observer_binding(self):
        ready = set()
        order = []

        def start(role):
            if role in ("controller", "sender"):
                self.assertIn("observer", ready, "최초 요청 전 독립 관측기 bind가 필요합니다")
            order.append(("start", role))

        def wait(name, deadline):
            self.assertEqual(deadline, 99)
            role = name.removesuffix("_ready.json")
            ready.add(role)
            order.append(("ready", role))

        g4.start_chain_workers(start, wait, 99)
        self.assertEqual(order[:3], [("start", "observer"), ("ready", "observer"), ("start", "controller")])

    def test_sut_error_and_actual_process_identity_are_preserved(self):
        record = {"role": "controller", "pid": 3, "status": "SUT_ERROR", "exit_code": 5}
        with self.assertRaises(g4.RunError) as caught:
            g4.check_worker_record("controller", 3, 5, record)
        self.assertEqual(caught.exception.status, "SUT_ERROR")
        with self.assertRaises(g4.RunError) as caught:
            g4.check_worker_record("controller", 4, 5, record)
        self.assertEqual(caught.exception.status, "TOOL_ERROR")

    def test_incomplete_run_or_cleanup_error_cannot_pass(self):
        checks = {"failures": [], "all_checks_passed": False}
        self.assertEqual(g4.final_status("COMPLETE", checks, []), "TOOL_ERROR")
        self.assertEqual(g4.final_status("SUT_ERROR", checks, []), "SUT_ERROR")
        self.assertEqual(g4.final_status("INTERRUPTED", {"failures": ["기한 초과"]}, ["정리 오류"]), "FAIL")

    def test_existing_directory_is_never_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError):
                g4.run(SimpleNamespace(output_dir=Path(directory)))

    def test_missing_vcan_cannot_start_carla_or_workers(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            with patch.object(g4, "inspect_link", side_effect=OSError("vcan 없음")), \
                    patch.object(g4.subprocess, "check_output", return_value="commit\n"), \
                    patch.object(g4.subprocess, "Popen") as spawn, \
                    patch.object(g4, "evaluate_g4", return_value={"all_checks_passed": False, "failures": []}), \
                    patch("builtins.print"):
                self.assertEqual(g4.run(SimpleNamespace(output_dir=output, interface="vcan0")), 2)
                spawn.assert_not_called()
            self.assertEqual(json.loads((output / "result.json").read_text())["status"], "ENV_ERROR")

    def test_isolated_help_and_exclusive_server_argument(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "not-created"
            command = [sys.executable, "-I", str(Path(g4.__file__).resolve())]
            result = subprocess.run(command + ["--help"], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run(command + ["--output-dir", str(output)], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
