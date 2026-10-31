"""Pure observation-rule checks; these do not constitute local CARLA evidence."""

import math
import struct
from types import SimpleNamespace
import unittest

from tools.g2_carla_smoke import (
    apply_brake_control, assess_motion, assess_preparation, classify_result, held_interval,
)


def observation(frame, stamp, speed, *, phase="brake", brake=1.0):
    return {
        "phase": phase, "frame": frame, "simulation_time_s": stamp,
        "host_monotonic_ns": 1000000000 + frame * 50000000,
        "speed_mps": speed,
        "applied_control": {"brake": brake, "throttle": 0.0, "steer": 0.0,
                            "hand_brake": False},
    }


class ControlTransitionTests(unittest.TestCase):
    def fake_carla(self):
        return SimpleNamespace(
            VehicleControl=lambda **values: values,
            command=SimpleNamespace(ApplyVehicleControl=lambda actor_id, control: (actor_id, control)),
        )

    def test_settle_ackermann_then_identical_brake_is_transmitted(self):
        class CachedVehicle:
            # Model the 0.9.15 client cache in Vehicle.cpp: Ackermann sends
            # independently and leaves the previous VehicleControl cached.
            id = 147

            def __init__(self):
                self.cached = None
                self.applied = None

            def apply_control(self, control):
                if control != self.cached:
                    self.applied = control
                    self.cached = control

            def apply_ackermann_control(self):
                self.applied = "ackermann"

        actor = CachedVehicle()
        brake = self.fake_carla().VehicleControl(throttle=0.0, brake=1.0, steer=0.0, hand_brake=False)
        actor.apply_control(brake)
        actor.apply_ackermann_control()
        actor.apply_control(brake)
        self.assertEqual(actor.applied, "ackermann")  # Original cache failure.

        calls = []
        def batch(commands, do_tick):
            calls.append((commands, do_tick))
            # Server batch dispatcher applies the command independently of
            # the Vehicle client's cached value. No world tick occurs here.
            actor.applied = commands[0][1]
            return [SimpleNamespace(actor_id=actor.id, error="")]

        reply = apply_brake_control(SimpleNamespace(apply_batch_sync=batch), actor, self.fake_carla())
        self.assertEqual(actor.applied, brake)
        self.assertEqual(len(calls), 1)
        self.assertFalse(calls[0][1])
        self.assertEqual(reply["actor_id"], actor.id)

    def test_missing_failed_or_wrong_actor_response_is_rejected(self):
        for responses in ([], [SimpleNamespace(actor_id=147, error="not found")],
                          [SimpleNamespace(actor_id=999, error="")]):
            with self.subTest(responses=responses):
                client = SimpleNamespace(apply_batch_sync=lambda *_: responses)
                with self.assertRaises(RuntimeError):
                    apply_brake_control(client, SimpleNamespace(id=147), self.fake_carla())


class HoldObservationTests(unittest.TestCase):
    def test_half_second_requires_eleven_samples(self):
        samples = [observation(i, i * 0.05, 0.0) for i in range(11)]
        self.assertIsNone(held_interval(samples[:10], lambda s: s["speed_mps"] <= 0.1, 0.5))
        self.assertEqual(held_interval(samples, lambda s: s["speed_mps"] <= 0.1, 0.5)["sample_count"], 11)

    def test_missing_frame_and_time_gap_break_continuity(self):
        contiguous = [observation(i, i * 0.05, 0.0) for i in range(11)]
        missing_frame = [s for s in contiguous if s["frame"] != 5]
        self.assertIsNone(held_interval(missing_frame, lambda _: True, 0.5))
        time_gap = [dict(s) for s in contiguous]
        for s in time_gap[5:]:
            s["simulation_time_s"] += 0.05
        self.assertIsNone(held_interval(time_gap, lambda _: True, 0.5))

    def test_above_threshold_and_nonfinite_speed_break_hold(self):
        for bad_speed in (0.100001, math.nan, math.inf):
            with self.subTest(speed=bad_speed):
                samples = [observation(i, i * 0.05, 0.0) for i in range(11)]
                samples[5]["speed_mps"] = bad_speed
                self.assertIsNone(held_interval(samples, lambda s: s["speed_mps"] <= 0.1, 0.5))


class MotionObservationTests(unittest.TestCase):
    def drive(self):
        return [observation(i, i * 0.05, 5.0 / 3.6, phase="drive", brake=0)
                for i in range(21)]

    def test_valid_observed_motion_and_braking(self):
        brake = [observation(21 + i, 1.05 + i * 0.05,
                             max(0.0, 1.2 - i * 0.12)) for i in range(41)]
        verdict = assess_motion(self.drive() + brake)
        self.assertTrue(verdict["actual_motion_observed"])
        self.assertEqual(verdict["initial_5kmh_held_1s"]["sample_count"], 21)
        self.assertEqual(verdict["first_brake_applied"]["frame"], 21)
        self.assertIsNotNone(verdict["stop_held_0_5s_within_2s"])

    def test_target_speed_without_observed_motion_is_not_success(self):
        samples = [observation(i, i * 0.05, 0.0, phase="drive", brake=0)
                   for i in range(30)]
        verdict = assess_motion(samples)
        self.assertFalse(verdict["actual_motion_observed"])
        self.assertIsNone(verdict["initial_5kmh_held_1s"])
        self.assertIsNone(verdict["first_brake_applied"])

    def test_command_without_applied_brake_is_not_success(self):
        samples = self.drive() + [observation(21 + i, 1.05 + i * 0.05, 0.0, brake=0)
                                  for i in range(41)]
        verdict = assess_motion(samples)
        self.assertIsNone(verdict["first_brake_applied"])
        self.assertIsNone(verdict["stop_held_0_5s_within_2s"])

    def test_stop_hold_must_complete_inside_two_second_window(self):
        # Applied at 1.05: zero speed starts at 2.60, so 0.5 s ends at 3.10.
        samples = self.drive() + [observation(21 + i, 1.05 + i * 0.05,
                                               0.0 if i >= 31 else 1.0)
                                  for i in range(45)]
        self.assertIsNone(assess_motion(samples)["stop_held_0_5s_within_2s"])

    def test_exact_two_second_window_boundary_is_included(self):
        samples = self.drive() + [observation(21 + i, 1.05 + i * 0.05,
                                               0.0 if i >= 30 else 1.0)
                                  for i in range(41)]
        self.assertIsNotNone(assess_motion(samples)["stop_held_0_5s_within_2s"])

    def test_carla_float32_step_keeps_exact_40_frame_boundary(self):
        step = struct.unpack("f", struct.pack("f", 0.05))[0]
        # CARLA's serialized fixed delta makes forty steps slightly > 2.0.
        self.assertGreater(step * 40, 2.0)
        brake = [observation(21 + i, 1.05 + i * step, 0.0 if i >= 30 else 1.0)
                 for i in range(41)]
        self.assertIsNotNone(assess_motion(self.drive() + brake)["stop_held_0_5s_within_2s"])
        # The next frame is outside the unchanged forty-interval window.
        late = [observation(21 + i, 1.05 + i * step, 0.0 if i >= 31 else 1.0)
                for i in range(42)]
        self.assertIsNone(assess_motion(self.drive() + late)["stop_held_0_5s_within_2s"])


class PreparationDeadlineTests(unittest.TestCase):
    def stable_samples(self):
        return [observation(i, i * 0.05, 5.0 / 3.6, phase="drive", brake=0)
                for i in range(21)]

    def test_stability_established_by_late_tick_cannot_be_ready(self):
        samples = self.stable_samples()
        deadline = 30_000_000_000
        # The final tick began before 30 s, but its observation returned late.
        samples[-1]["host_monotonic_ns"] = deadline + 1
        progress = assess_preparation(samples, deadline, checked_ns=deadline + 2)
        self.assertIsNotNone(progress["observed_stable_interval"])
        self.assertEqual(progress["status"], "TIMED_OUT")
        self.assertIsNone(progress["completed_monotonic_ns"])
        self.assertEqual(progress["last_observation_monotonic_ns"], deadline + 1)

    def test_post_observation_deadline_is_checked_even_when_observation_was_timely(self):
        deadline = 30_000_000_000
        progress = assess_preparation(self.stable_samples(), deadline, checked_ns=deadline + 1)
        self.assertEqual(progress["status"], "TIMED_OUT")
        self.assertEqual(progress["deadline_overrun_ns"], 1)

    def test_stable_completion_at_deadline_is_recorded(self):
        deadline = 30_000_000_000
        progress = assess_preparation(self.stable_samples(), deadline, checked_ns=deadline)
        self.assertEqual(progress["status"], "READY")
        self.assertEqual(progress["completed_monotonic_ns"], deadline)
        self.assertEqual(progress["deadline_monotonic_ns"], deadline)


class ResultClassificationTests(unittest.TestCase):
    def test_motion_failure_survives_cleanup_error(self):
        result = classify_result("COMPLETE", "FAIL", ["actor destroy failed"])
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["motion_status"], "FAIL")
        self.assertEqual(result["execution_status"], "COMPLETE")
        self.assertEqual(result["cleanup_status"], "FAIL")

    def test_motion_success_with_cleanup_error_cannot_pass(self):
        result = classify_result("COMPLETE", "PASS", ["settings restore failed"])
        self.assertEqual(result["status"], "ENV_ERROR")
        self.assertEqual(result["motion_status"], "PASS")
        self.assertEqual(result["cleanup_status"], "FAIL")

    def test_ready_motion_and_successful_cleanup_can_pass(self):
        self.assertEqual(classify_result("COMPLETE", "PASS", [])["status"], "PASS")

    def test_incomplete_execution_cannot_pass_on_motion_check_alone(self):
        result = classify_result("INTERRUPTED", "PASS", [])
        self.assertEqual(result["status"], "INTERRUPTED")


if __name__ == "__main__":
    unittest.main()
