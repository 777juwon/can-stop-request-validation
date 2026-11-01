"""본시험 계획과 재개 보호 검사다. 서버나 실제 CAN을 실행하지 않는다."""

from collections import Counter
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import main_campaign as campaign
from tools import main_plan as plan
from tools import g4_carla_smoke as g4
from tools.g4_carla_smoke import worker_arguments


class PlanTests(unittest.TestCase):
    def test_eighty_unique_ids_ten_per_cell_and_alternating_pair_order(self):
        rows = plan.load_rows()
        self.assertEqual(len({row["run_id"] for row in rows}), 80)
        self.assertEqual(set(Counter((row["scenario"], row["variant"]) for row in rows).values()), {10})
        for left, right in zip(rows[::2], rows[1::2]):
            self.assertEqual(left["paired_run_id"], right["run_id"])
            self.assertEqual(left["pair_id"], right["pair_id"])
            self.assertEqual([left["variant"], right["variant"]], ["A", "B"] if left["repeat"] % 2 else ["B", "A"])

    def test_baseline_values_cannot_be_relaxed(self):
        for key, value in (("timeout_ms", 300), ("stop_window_s", 3), ("fixed_delta_seconds", .1),
                           ("input_duration_s", 10), ("spawn_index", 0), ("sticky_control", False)):
            config = plan.load_config()
            config[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                plan.validate_config(config)

    def test_physics_reference_is_existing_observation_and_position_is_excluded_only(self):
        config = plan.load_config()
        reference = json.loads((plan.ROOT / config["physics_reference"]).read_text())
        self.assertEqual(plan.physics_digest(reference["vehicle_physics"]), config["physics_normalized_sha256"])
        a = "mass=1845 position=Vector3D(x=1, y=2, z=3)"
        b = "mass=1845 position=Vector3D(x=7, y=8, z=9)"
        self.assertEqual(plan.physics_digest(a), plan.physics_digest(b))
        self.assertNotEqual(plan.physics_digest(a), plan.physics_digest(b.replace("1845", "1500")))

    def test_variant_and_scenario_are_forwarded_to_real_worker_command(self):
        argv = worker_arguments("controller", "vcan0", Path("new"), 0, "B", "T-04")
        self.assertEqual(argv[argv.index("--variant") + 1], "B")
        self.assertEqual(argv[argv.index("--scenario") + 1], "T-04")
        self.assertEqual(argv[argv.index("--run-token") + 1], "0")

    def test_output_and_rows_cannot_escape_project_or_change_ids(self):
        with self.assertRaises(ValueError):
            plan.project_output("/tmp/outside-main-run")
        rows = [{**row, "run_token": i} for i, row in enumerate(plan.load_rows())]
        rows[0]["run_id"] = "../../outside"
        with self.assertRaises(ValueError):
            plan.verify_run_rows(rows)


class CampaignTests(unittest.TestCase):
    def prepare(self, directory):
        return campaign.prepare(Path(directory) / "campaign")

    def fake_vehicle(self, args, *, status="COMPLETE", fail=False, cleanup="PASS"):
        args.output_dir.mkdir()
        result = {"scope": "MAIN_CARLA_ORIGINAL_ATTEMPT", "execution_status": status, "cleanup_status": cleanup,
                  "main_trials_executed": 1, "checks": {"evidence_valid": status == "COMPLETE", "operational_failures": [],
                  "requirements": {"R-04": {"status": "FAIL" if fail else "PASS"}}}}
        meta = {"run_id": args.planned_run["run_id"], "run_token": args.run_token,
                "config_sha256": plan.digest(plan.canonical(args.main_config))}
        (args.output_dir / "result.json").write_text(json.dumps(result))
        (args.output_dir / "metadata.json").write_text(json.dumps(meta))

    def test_prepare_snapshots_eighty_unique_tokens_without_running_vehicle(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(campaign, "run_vehicle") as vehicle:
            manifest = self.prepare(directory)
            self.assertEqual(len(set(row["run_token"] for row in manifest["runs"])), 80)
            plan.verify_frozen(manifest)
            vehicle.assert_not_called()
            self.assertEqual(campaign.status(Path(directory) / "campaign", manifest)["original_attempted"], 0)

    def test_changed_source_config_fixture_or_token_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            original = self.prepare(directory)
            for kind in ("source", "config", "fixture", "token"):
                manifest = copy.deepcopy(original)
                if kind == "source":
                    manifest["source_sha256"]["tools/main_plan.py"] = "0" * 64
                elif kind == "config":
                    manifest["config"]["timeout_ms"] = 300
                elif kind == "fixture":
                    manifest["fixture_sha256"]["T-01"] = "0" * 64
                else:
                    manifest["runs"][1]["run_token"] = manifest["runs"][0]["run_token"]
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    plan.verify_frozen(manifest)

    def test_original_claim_is_not_reused_after_interruption(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.prepare(directory)
            root = Path(directory) / "campaign"
            row = manifest["runs"][0]
            claim = {"run_id": row["run_id"], "run_token": row["run_token"], "config_sha256": manifest["config_sha256"]}
            campaign.atomic_write_json(root / "attempts" / (row["run_id"] + ".json"), claim)
            report = campaign.status(root, manifest)
            self.assertEqual((report["original_attempted"], report["original_completed"]), (1, 0))
            self.assertEqual(report["runs"][0]["execution_status"], "RESULT_NOT_RECORDED")
            with patch.object(campaign, "run_vehicle") as vehicle, self.assertRaises(FileExistsError):
                campaign.execute_one(root, manifest, row, False)
            vehicle.assert_not_called()
            with patch.object(campaign, "run_vehicle", side_effect=self.fake_vehicle):
                report = campaign.run_campaign(root, manifest, 1, False)
            self.assertEqual(report["runs"][0]["execution_status"], "RESULT_NOT_RECORDED")
            self.assertEqual(report["runs"][1]["execution_status"], "COMPLETE")

    def test_requirement_failure_is_preserved_and_next_original_can_run(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.prepare(directory)
            root = Path(directory) / "campaign"
            with patch.object(campaign, "run_vehicle", side_effect=lambda args: self.fake_vehicle(args, fail=True)):
                report = campaign.run_campaign(root, manifest, 2, False)
            self.assertEqual((report["original_attempted"], report["original_completed"], report["requirement_fail_count"]), (2, 2, 2))
            self.assertEqual(report["not_started"], 78)

    def test_environment_error_stops_batch_and_resume_skips_failed_id(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.prepare(directory)
            root = Path(directory) / "campaign"
            with patch.object(campaign, "run_vehicle", side_effect=lambda args: self.fake_vehicle(args, status="ENV_ERROR")):
                report = campaign.run_campaign(root, manifest, 80, False)
            self.assertEqual((report["original_attempted"], report["not_started"]), (1, 79))
            self.assertTrue(report["batch_halted"])
            with patch.object(campaign, "run_vehicle", side_effect=self.fake_vehicle):
                report = campaign.run_campaign(root, manifest, 1, False)
            self.assertEqual(report["runs"][0]["execution_status"], "ENV_ERROR")
            self.assertEqual(report["runs"][1]["execution_status"], "COMPLETE")
            self.assertFalse(report["batch_halted"])

    def test_cleanup_failure_stops_and_is_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.prepare(directory)
            root = Path(directory) / "campaign"
            with patch.object(campaign, "run_vehicle", side_effect=lambda args: self.fake_vehicle(args, cleanup="FAIL")):
                report = campaign.run_campaign(root, manifest, 80, False)
            self.assertEqual(report["original_attempted"], 1)
            self.assertEqual(report["runs"][0]["execution_status"], "CLEANUP_ERROR")

    def test_isolated_help_and_exclusive_server_flag_guard(self):
        command = [sys.executable, "-I", str(Path(campaign.__file__).resolve())]
        result = subprocess.run(command + ["--help"], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(command + ["check", "--output-dir", directory,
                                   "--variant", "B", "--scenario", "T-04"], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2)

    def test_real_coordinator_records_preflight_error_without_starting_workers(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            args = SimpleNamespace(output_dir=output, interface="vcan0", main_config=plan.load_config(),
                                   original_main_run=True, variant="B", scenario="T-04", run_token=0)
            with patch.object(g4, "inspect_link", side_effect=OSError("가상 장치 없음")), \
                    patch.object(g4.subprocess, "check_output", return_value="test-commit\n"), \
                    patch.object(g4.subprocess, "Popen") as workers, patch("builtins.print"):
                code = g4.run(args)
                workers.assert_not_called()
            result = json.loads((output / "result.json").read_text())
            metadata = json.loads((output / "metadata.json").read_text())
            self.assertEqual(code, 2)
            self.assertEqual(result["status"], "ENV_ERROR")
            self.assertEqual(metadata["execution_status"], result["execution_status"])
            self.assertEqual(result["main_trials_executed"], 1)
            self.assertEqual(result["scope"], "MAIN_CARLA_ORIGINAL_ATTEMPT")
            self.assertEqual(result, json.loads((output / "verdict.json").read_text()))
            self.assertEqual(result["checks"]["failures"], [])

    def test_original_attempt_without_fixed_config_is_rejected_before_output_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            with self.assertRaises(ValueError):
                g4.run(SimpleNamespace(output_dir=output, original_main_run=True))
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
