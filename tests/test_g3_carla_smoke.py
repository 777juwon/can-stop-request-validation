"""G3 실행기의 분류와 실행 전 보호 장치를 검사한다. 차량 실행은 하지 않는다."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import g3_carla_smoke as g3


class IntegrationResultTests(unittest.TestCase):
    def test_known_failure_survives_interruption_and_cleanup_error(self):
        checks = {"all_checks_passed": False, "failures": ["호출 지연"]}
        self.assertEqual(g3.final_status("INTERRUPTED", checks, ["정리 오류"]), "FAIL")

    def test_partial_evidence_cannot_pass(self):
        checks = {"all_checks_passed": False, "failures": []}
        self.assertEqual(g3.final_status("ENV_ERROR", checks, []), "ENV_ERROR")
        self.assertEqual(g3.final_status("COMPLETE", checks, []), "TOOL_ERROR")

    def test_all_checks_and_cleanup_required_for_pass(self):
        checks = {"all_checks_passed": True, "failures": []}
        self.assertEqual(g3.final_status("COMPLETE", checks, []), "PASS")
        self.assertEqual(g3.final_status("COMPLETE", checks, ["actor 남음"]), "TOOL_ERROR")

    def test_worker_failure_keeps_status_and_checks_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            self.assertEqual(g3.worker_failure(output, "sender", 4).status, "TOOL_ERROR")
            (output / "sender_result.json").write_text(json.dumps({"status": "INPUT_ERROR", "error": "슬롯 초과"}))
            self.assertEqual(g3.worker_failure(output, "sender", 4).status, "INPUT_ERROR")
            self.assertEqual(g3.worker_failure(output, "sender", 2).status, "TOOL_ERROR")

    def test_worker_completion_requires_matching_record_and_actual_exit(self):
        record = {"role": "observer", "pid": 41, "status": "COMPLETE", "exit_code": 0}
        g3.check_worker_record("observer", 41, 0, record)
        for changed in ({**record, "pid": 42}, {**record, "role": "sender"},
                        {**record, "exit_code": 2}, {**record, "status": "ENV_ERROR"}):
            with self.subTest(record=changed), self.assertRaises(g3.RunError) as caught:
                g3.check_worker_record("observer", 41, 0, changed)
            self.assertEqual(caught.exception.status, "TOOL_ERROR")
        with self.assertRaises(g3.RunError) as caught:
            g3.check_worker_record("observer", 41, 2,
                                   {"role": "observer", "pid": 41, "status": "ENV_ERROR", "exit_code": 2})
        self.assertEqual(caught.exception.status, "ENV_ERROR")


class IntegrationStartupTests(unittest.TestCase):
    def test_existing_output_directory_is_not_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError):
                g3.run(SimpleNamespace(output_dir=Path(directory)))

    def test_missing_vcan_preserves_metadata_without_carla_or_workers(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new-run"
            args = SimpleNamespace(output_dir=output, interface="vcan0")
            with patch.object(g3, "inspect_link", side_effect=OSError("vcan0 없음")), \
                    patch.object(g3.subprocess, "run", return_value=SimpleNamespace(stdout="testcommit\n")), \
                    patch.object(g3.subprocess, "Popen") as spawn, \
                    patch.object(g3, "evaluate_integration", return_value={"failures": [], "all_checks_passed": False}), \
                    patch("builtins.print"):
                self.assertEqual(g3.run(args), 2)
                spawn.assert_not_called()
            metadata = json.loads((output / "metadata.json").read_text())
            result = json.loads((output / "result.json").read_text())
            self.assertEqual(metadata["execution_status"], "ENV_ERROR")
            self.assertEqual(result["status"], "ENV_ERROR")
            self.assertNotIn("actor_id", metadata)
            self.assertEqual(json.loads((output / "commands.json").read_text()), [])

    def test_exclusive_server_flag_required_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "not-created"
            result = subprocess.run([sys.executable, "-I", str(Path(g3.__file__).resolve()),
                                     "--output-dir", str(output)], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())

    def test_isolated_help_imports_local_modules_without_starting_carla(self):
        result = subprocess.run([sys.executable, "-I", str(Path(g3.__file__).resolve()), "--help"],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--exclusive-server", result.stdout)


if __name__ == "__main__":
    unittest.main()
