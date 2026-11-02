"""사진의 원본 추적, 결측 거부와 서버 종료 판정을 점검한다."""

import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools import capture_carla_illustrations as capture


def fixture():
    meta = {"t0_ns": 10_000_000_000, "trial_end_ns": 30_000_000_000}
    sample = {"phase": "g4", "host_monotonic_ns": 19_020_000_000, "frame": 101,
              "simulation_time_s": 2000., "transform": dict(x=1., y=2., z=0., pitch=0., yaw=0., roll=0.),
              "speed_mps": 0., "velocity_mps": dict(x=0., y=0., z=0.),
              "applied_control": {"brake": 1.}}
    result = {"checks": {"requirements": {"R-07": {"status": "PASS"}},
                         "metrics": {"stop_hold": {"last_frame": 101}}}}
    return meta, result, [sample]


class SourceSelectionTests(unittest.TestCase):
    def test_initial_spawn_clearance_does_not_change_recorded_pose(self):
        _, _, samples = fixture()
        recorded = samples[0]["transform"]
        raised = capture.initial_spawn_pose(recorded)
        self.assertEqual(recorded["z"], 0.)
        self.assertEqual(raised, {**recorded, "z": 1.5})

    def test_host_selection_never_uses_simulation_clock(self):
        meta, result, samples = fixture()
        chosen = capture.selected_sample(meta, result, samples, 9.)
        self.assertEqual(chosen["frame"], 101)
        samples[0]["simulation_time_s"] = 1_000_000.
        self.assertEqual(capture.selected_sample(meta, result, samples, 9.)["frame"], 101)

    def test_late_missing_sample_and_post_trial_sample_are_rejected(self):
        for stamp in (19_100_000_001, 31_000_000_000):
            meta, result, samples = fixture()
            samples[0]["host_monotonic_ns"] = stamp
            with self.assertRaises((ValueError, StopIteration)):
                capture.selected_sample(meta, result, samples, 9.)

    def test_stop_image_requires_original_pass_and_observed_brake(self):
        meta, result, samples = fixture()
        self.assertEqual(capture.selected_sample(meta, result, samples, "stop_hold")["frame"], 101)
        for field, value in (("speed_mps", 1.), ("applied_control", {"brake": 0.})):
            altered = copy.deepcopy(samples)
            altered[0][field] = value
            with self.assertRaises(ValueError):
                capture.selected_sample(meta, result, altered, "stop_hold")
        result["checks"]["requirements"]["R-07"]["status"] = "FAIL"
        with self.assertRaises(ValueError):
            capture.selected_sample(meta, result, samples, "stop_hold")

    def test_nonfinite_pose_and_inconsistent_original_speed_rejected(self):
        for target in ("pose", "speed"):
            meta, result, samples = fixture()
            if target == "pose":
                samples[0]["transform"]["x"] = float("nan")
            else:
                samples[0]["speed_mps"] = 2.
            with self.assertRaises(ValueError):
                capture.selected_sample(meta, result, samples, 9.)


class ShutdownTests(unittest.TestCase):
    def test_destroy_verification_refreshes_snapshot_before_actor_lookup(self):
        world = Mock()
        world.tick.return_value = 501
        world.get_actors.side_effect = lambda: [] if world.tick.called else [Mock()]
        world.get_settings.return_value.synchronous_mode = False
        frame, remaining, synchronous = capture.restore_world(world, "original", "weather")
        self.assertEqual((frame, remaining, synchronous), (501, [], False))
        methods = [call[0] for call in world.mock_calls]
        self.assertLess(methods.index("tick"), methods.index("get_actors"))
        self.assertLess(methods.index("tick"), methods.index("apply_settings"))

    def test_closed_ports_alone_cannot_make_crash_normal(self):
        result = capture.shutdown_verdict(-11, "Signal 11 caught", [], [], [])
        self.assertEqual((result["status"], result["shell_equivalent_code"]), ("NOT_NORMAL", 139))

    def test_clean_exit_requires_no_fatal_markers_ports_or_owned_processes(self):
        self.assertEqual(capture.shutdown_verdict(0, "", [], [], [])["status"], "PASS")
        for args in ((139, "", [], [], []), (0, "Fatal error", [], [], []),
                     (0, "", [2000], [], []), (0, "", [], [{"pid": 1}], []),
                     (0, "", [], [], ["SIGTERM"]), (None, "", [], [], [])):
            with self.subTest(args=args):
                self.assertEqual(capture.shutdown_verdict(*args)["status"], "NOT_NORMAL")


class RuntimeGuardTests(unittest.TestCase):
    def test_readiness_uses_new_client_after_failed_connection(self):
        first, second = Mock(), Mock()
        first.get_server_version.side_effect = RuntimeError("연결 대기 오류")
        second.get_server_version.return_value = "0.9.15"
        carla, process, report = Mock(), Mock(), {}
        carla.Client.side_effect = [first, second]
        process.poll.return_value = None
        with patch.object(capture, "ports_open", return_value=[2000]), patch.object(capture.time, "sleep"):
            client, version = capture.wait_ready(carla, process, report)
        self.assertIs(client, second)
        self.assertEqual(version, "0.9.15")
        self.assertEqual(report["readiness_errors"], ["연결 대기 오류"])

    def test_existing_output_and_original_folder_refused_before_server_checks(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(capture, "ROOT", Path(directory)), \
                patch.object(capture, "ports_open") as ports:
            root = Path(directory)
            for path in (root, root / "runs" / "new"):
                with self.assertRaises((ValueError, FileExistsError)):
                    capture.execute(path)
            ports.assert_not_called()

    def test_existing_server_is_not_attached_or_signalled(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(capture, "ROOT", Path(directory)), \
                patch.object(capture, "ports_open", return_value=[2000]), \
                patch.object(capture.subprocess, "Popen") as start:
            with self.assertRaises(RuntimeError):
                capture.execute(Path(directory) / "new")
            start.assert_not_called()

    def test_altered_archive_aborts(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(capture, "ROOT", Path(directory)):
            p = Path(directory) / "input.json"
            p.write_text("{}")
            expected = capture.sha(p)
            self.assertEqual(capture.audit_inputs({"input.json": expected})["status"], "PASS")
            p.write_text("[]")
            with self.assertRaises(ValueError):
                capture.audit_inputs({"input.json": expected})


if __name__ == "__main__":
    unittest.main()
