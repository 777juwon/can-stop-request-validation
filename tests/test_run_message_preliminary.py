"""예비시험 실행 전 보호 장치 검사다. CAN socket을 열지 않는다."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import run_message_preliminary as trial


class TrialGuardTests(unittest.TestCase):
    def test_output_directory_is_never_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError):
                trial.run_case(Path(directory), "vcan0", "A", "T-01")

    def test_failed_preflight_never_starts_workers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "new"
            with patch.object(trial, "inspect_link", side_effect=OSError("장치 없음")), \
                    patch.object(trial.subprocess, "check_output", return_value="commit\n"), \
                    patch.object(trial.subprocess, "Popen") as spawn:
                result = trial.run_case(path, "vcan0", "A", "T-01")
            spawn.assert_not_called()
            self.assertEqual(result["execution_status"], "ENV_ERROR")
            self.assertFalse(result["checks"]["evidence_valid"])
            self.assertEqual(json.loads((path / "commands.json").read_text()), [])

    def test_isolated_help_and_existing_campaign_guard(self):
        command = [sys.executable, "-I", str(Path(trial.__file__).resolve())]
        result = subprocess.run(command + ["--help"], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(command + ["--output-dir", directory], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
