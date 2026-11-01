"""A 방식 상태 기계의 가짜 시각 검사다. 실제 vCAN/CARLA 시험이 아니다."""

import struct
import unittest

from tools.g4_controller_core import (
    ARMED, INIT_INHIBITED, INIT_REASON, NEAR_DISTANCE, NORMAL, RX_TIMEOUT,
    STOP_LATCHED, DistanceTimeoutController, G4ArmError,
)


TOKEN = 0x12345678
MS = 1_000_000


def distance_frame(distance=1000, counter=0, valid=1, token=TOKEN, *, can_id=0x100, dlc=8):
    return struct.pack("=IB3x8s", can_id, dlc,
                       struct.pack("<HBBI", distance, counter, valid, token))


def prepared_controller():
    controller = DistanceTimeoutController(TOKEN, 0)
    for counter in range(5):
        controller.on_frame(distance_frame(counter=counter), counter * 50 * MS)
    return controller


def armed_controller():
    controller = prepared_controller()
    controller.arm(200 * MS)
    return controller


class ControllerStartupTests(unittest.TestCase):
    def test_startup_has_explicit_stop_and_no_input(self):
        controller = DistanceTimeoutController(TOKEN, 10)
        self.assertEqual((controller.state, controller.stop, controller.reason),
                         (INIT_INHIBITED, True, INIT_REASON))
        self.assertIsNone(controller.last_valid_rx_ns)
        self.assertIsNone(controller.distance_cm)
        self.assertEqual(controller.valid_normal_count, 0)
        self.assertEqual(controller.events[0]["host_monotonic_ns"], 10)
        self.assertIsNone(controller.events[0]["from_state"])

    def test_no_input_remains_inhibited_even_after_preparation_deadline(self):
        controller = DistanceTimeoutController(TOKEN, 0)
        controller.poll(31_000 * MS)
        self.assertEqual((controller.state, controller.stop, controller.reason),
                         (INIT_INHIBITED, True, INIT_REASON))
        with self.assertRaises(G4ArmError):
            controller.arm(31_000 * MS)
        self.assertEqual(controller.events[-1]["action"], "STARTUP_EXPIRED")

    def test_arm_requires_at_least_five_valid_far_inputs(self):
        controller = DistanceTimeoutController(TOKEN, 0)
        for counter in range(4):
            controller.on_frame(distance_frame(counter=counter), counter * 50 * MS)
        with self.assertRaises(G4ArmError):
            controller.arm(150 * MS)
        self.assertTrue(controller.stop)
        controller.on_frame(distance_frame(counter=4), 200 * MS)
        self.assertIsNone(controller.arm(200 * MS))
        self.assertEqual((controller.state, controller.stop, controller.reason),
                         (ARMED, False, NORMAL))

    def test_near_inputs_do_not_count_as_normal_startup_frames(self):
        controller = DistanceTimeoutController(TOKEN, 0)
        for counter in range(5):
            controller.on_frame(distance_frame(distance=200, counter=counter), counter * 50 * MS)
        self.assertEqual(controller.valid_normal_count, 0)
        with self.assertRaises(G4ArmError):
            controller.arm(200 * MS)
        self.assertEqual(controller.reason, INIT_REASON)

    def test_last_input_must_still_be_far_after_five_normal_frames(self):
        controller = prepared_controller()
        controller.on_frame(distance_frame(distance=199, counter=5), 250 * MS)
        with self.assertRaises(G4ArmError):
            controller.arm(250 * MS)
        self.assertEqual(controller.events[-1]["action"], "NEAR_INPUT")
        self.assertTrue(controller.stop)

    def test_arm_freshness_is_strictly_less_than_200ms(self):
        fresh = prepared_controller()
        fresh.arm(399 * MS)
        self.assertFalse(fresh.stop)
        stale = prepared_controller()
        with self.assertRaises(G4ArmError):
            stale.arm(400 * MS)
        self.assertEqual(stale.events[-1]["action"], "STALE_INPUT")
        self.assertEqual(stale.state, INIT_INHIBITED)

    def test_arm_preparation_deadline_is_strictly_less_than_30_seconds(self):
        for now, succeeds in ((30_000 * MS - 1, True), (30_000 * MS, False)):
            controller = prepared_controller()
            controller.on_frame(distance_frame(counter=5), 29_950 * MS)
            with self.subTest(now=now):
                if succeeds:
                    controller.arm(now)
                    self.assertFalse(controller.stop)
                else:
                    with self.assertRaises(G4ArmError):
                        controller.arm(now)
                    self.assertEqual(controller.events[-1]["action"], "STARTUP_EXPIRED")

    def test_arm_does_not_reset_watchdog_to_arm_time(self):
        controller = prepared_controller()
        controller.arm(399 * MS)
        controller.poll(400 * MS)
        self.assertEqual((controller.state, controller.reason), (STOP_LATCHED, RX_TIMEOUT))

    def test_second_arm_is_rejected_without_reinitializing_run(self):
        controller = armed_controller()
        with self.assertRaises(G4ArmError):
            controller.arm(201 * MS)
        self.assertEqual(controller.state, ARMED)
        self.assertEqual(controller.last_valid_rx_ns, 200 * MS)


class ControllerTimingTests(unittest.TestCase):
    def test_watchdog_199ms_and_200ms_boundary(self):
        controller = armed_controller()
        self.assertIsNone(controller.poll(399 * MS))
        self.assertEqual((controller.state, controller.reason, controller.stop), (ARMED, NORMAL, False))
        controller.poll(400 * MS)
        self.assertEqual((controller.state, controller.reason, controller.stop),
                         (STOP_LATCHED, RX_TIMEOUT, True))
        self.assertEqual(controller.events[-1]["host_monotonic_ns"], 400 * MS)

    def test_background_heartbeat_does_not_extend_watchdog(self):
        controller = armed_controller()
        for now in (250, 300, 350, 399, 400):
            event = controller.on_frame(distance_frame(can_id=0x101), now * MS)
            self.assertEqual(event["action"], "IGNORE_BACKGROUND")
            self.assertFalse(event["accepted"])
        self.assertEqual(controller.last_valid_rx_ns, 200 * MS)
        self.assertEqual(controller.reason, RX_TIMEOUT)

    def test_late_recovery_cannot_hide_timeout_without_prior_poll(self):
        controller = armed_controller()
        event = controller.on_frame(distance_frame(counter=5), 400 * MS)
        self.assertTrue(event["accepted"])
        self.assertEqual(controller.last_valid_rx_ns, 400 * MS)
        self.assertEqual((controller.state, controller.reason), (STOP_LATCHED, RX_TIMEOUT))
        self.assertEqual(controller.events[-2]["event"], "state_transition")
        self.assertEqual(controller.events[-2]["last_valid_rx_ns"], 200 * MS)

    def test_frame_before_timeout_refreshes_receive_age(self):
        controller = armed_controller()
        controller.on_frame(distance_frame(counter=5), 399 * MS)
        controller.poll(400 * MS)
        self.assertFalse(controller.stop)
        controller.poll(599 * MS)
        self.assertEqual(controller.reason, RX_TIMEOUT)

    def test_same_counter_repeated_frames_are_new_receptions_in_a(self):
        controller = armed_controller()
        for now in (250, 300, 350, 400, 450, 500, 550):
            event = controller.on_frame(distance_frame(counter=4), now * MS)
            self.assertTrue(event["accepted"])
            self.assertEqual(controller.last_valid_rx_ns, now * MS)
            self.assertFalse(controller.stop)
        controller.poll(749 * MS)
        self.assertFalse(controller.stop)
        controller.poll(750 * MS)
        self.assertEqual(controller.reason, RX_TIMEOUT)

    def test_counter_progress_wrap_and_jump_add_no_sequence_watchdog(self):
        controller = armed_controller()
        for now, counter in zip((250, 300, 350, 400, 450), (255, 0, 0, 200, 1)):
            controller.on_frame(distance_frame(counter=counter), now * MS)
            self.assertEqual(controller.last_counter, counter)
            self.assertFalse(controller.stop)


class ControllerNearAndLatchTests(unittest.TestCase):
    def test_near_threshold_includes_zero_and_200_but_not_201(self):
        for distance, should_stop in ((0, True), (199, True), (200, True), (201, False)):
            controller = armed_controller()
            controller.on_frame(distance_frame(distance=distance, counter=5), 250 * MS)
            with self.subTest(distance=distance):
                self.assertEqual(controller.stop, should_stop)
                self.assertEqual(controller.reason, NEAR_DISTANCE if should_stop else NORMAL)

    def test_timeout_wins_when_near_frame_arrives_at_expiration(self):
        controller = armed_controller()
        controller.on_frame(distance_frame(distance=200, counter=5), 400 * MS)
        self.assertEqual(controller.reason, RX_TIMEOUT)
        transitions = [event for event in controller.events if event["event"] == "state_transition"]
        self.assertEqual([event["reason"] for event in transitions], [INIT_REASON, NORMAL, RX_TIMEOUT])

    def test_first_near_reason_survives_later_timeout_and_recovery(self):
        controller = armed_controller()
        controller.on_frame(distance_frame(distance=200, counter=5), 250 * MS)
        controller.poll(450 * MS)
        controller.on_frame(distance_frame(counter=6), 500 * MS)
        self.assertEqual((controller.state, controller.stop, controller.reason),
                         (STOP_LATCHED, True, NEAR_DISTANCE))
        self.assertEqual(controller.distance_cm, 1000)
        with self.assertRaises(G4ArmError):
            controller.arm(500 * MS)
        self.assertEqual(controller.reason, NEAR_DISTANCE)

    def test_timeout_reason_survives_recovery_and_later_near_input(self):
        controller = armed_controller()
        controller.poll(400 * MS)
        controller.on_frame(distance_frame(counter=5), 450 * MS)
        controller.on_frame(distance_frame(distance=0, counter=6), 500 * MS)
        controller.poll(900 * MS)
        self.assertEqual((controller.state, controller.reason), (STOP_LATCHED, RX_TIMEOUT))
        self.assertEqual(len([event for event in controller.events
                              if event["event"] == "state_transition"]), 3)

    def test_new_run_uses_new_object_with_startup_inhibition(self):
        old = armed_controller()
        old.poll(400 * MS)
        new = DistanceTimeoutController(TOKEN + 1, 500 * MS)
        self.assertEqual((new.state, new.reason, new.valid_normal_count),
                         (INIT_INHIBITED, INIT_REASON, 0))
        self.assertIsNone(new.last_valid_rx_ns)
        self.assertEqual(old.state, STOP_LATCHED)
        self.assertFalse(hasattr(old, "reset"))


class ControllerFrameValidationTests(unittest.TestCase):
    def test_independent_known_little_endian_fixture(self):
        controller = DistanceTimeoutController(TOKEN, 0)
        event = controller.on_frame(bytes.fromhex("0001000008000000e803ab0178563412"), 123)
        self.assertTrue(event["accepted"])
        self.assertEqual((controller.distance_cm, controller.last_counter), (1000, 0xAB))
        self.assertEqual(event["input_run_token"], TOKEN)
        self.assertEqual(event["raw_frame_hex"], "0001000008000000e803ab0178563412")

    def test_maximum_distance_is_valid(self):
        controller = DistanceTimeoutController(TOKEN, 0)
        event = controller.on_frame(distance_frame(distance=10_000), 0)
        self.assertTrue(event["accepted"])
        self.assertEqual(controller.distance_cm, 10_000)

    def test_invalid_frames_do_not_update_distance_counter_count_or_watchdog(self):
        cases = (
            (bytes(15), "REJECT_LENGTH"),
            (bytes(72), "REJECT_LENGTH"),
            (distance_frame(dlc=7), "REJECT_DLC"),
            (distance_frame(dlc=9), "REJECT_DLC"),
            (distance_frame(can_id=0x80000100), "REJECT_FLAGS"),
            (distance_frame(can_id=0x40000100), "REJECT_FLAGS"),
            (distance_frame(can_id=0x20000100), "REJECT_FLAGS"),
            (distance_frame(can_id=0x800), "REJECT_FLAGS"),
            (distance_frame(can_id=0x200), "IGNORE_ID"),
            (distance_frame(can_id=0x101), "IGNORE_BACKGROUND"),
            (distance_frame(token=TOKEN + 1), "REJECT_TOKEN"),
            (distance_frame(valid=0), "REJECT_VALID"),
            (distance_frame(valid=2), "REJECT_VALID"),
            (distance_frame(distance=10_001), "REJECT_DISTANCE"),
            (distance_frame(distance=65_535), "REJECT_DISTANCE"),
        )
        for raw, action in cases:
            controller = armed_controller()
            before = controller.snapshot()
            event = controller.on_frame(raw, 399 * MS)
            with self.subTest(action=action, raw=raw.hex()):
                self.assertEqual(event["action"], action)
                self.assertFalse(event["accepted"])
                for key in ("distance_cm", "last_counter", "valid_normal_count", "last_valid_rx_ns"):
                    self.assertEqual(controller.snapshot()[key], before[key])
                self.assertFalse(controller.stop)
                controller.poll(400 * MS)
                self.assertEqual(controller.reason, RX_TIMEOUT)

    def test_invalid_frame_at_deadline_still_checks_timeout(self):
        controller = armed_controller()
        event = controller.on_frame(distance_frame(valid=0), 400 * MS)
        self.assertEqual(event["action"], "REJECT_VALID")
        self.assertEqual((event["stop"], event["reason"]), (True, RX_TIMEOUT))
        self.assertEqual(controller.last_valid_rx_ns, 200 * MS)

    def test_rejected_input_fields_remain_in_diagnostic(self):
        controller = armed_controller()
        event = controller.on_frame(distance_frame(distance=10_001, counter=77), 250 * MS)
        self.assertEqual((event["distance_cm"], event["counter"]), (10_001, 77))
        self.assertEqual((controller.distance_cm, controller.last_counter), (1000, 4))

    def test_foreign_run_frames_do_not_satisfy_startup_count(self):
        controller = DistanceTimeoutController(TOKEN, 0)
        for counter in range(5):
            controller.on_frame(distance_frame(token=TOKEN + 1, counter=counter), counter * 50 * MS)
        self.assertEqual(controller.valid_normal_count, 0)
        self.assertIsNone(controller.last_valid_rx_ns)
        with self.assertRaises(G4ArmError):
            controller.arm(200 * MS)

    def test_wrong_raw_type_is_explicit_and_does_not_mutate_state(self):
        controller = armed_controller()
        before, count = controller.snapshot(), len(controller.events)
        for raw in (None, bytearray(distance_frame()), memoryview(distance_frame()), "frame", True):
            with self.subTest(raw_type=type(raw)), self.assertRaises(TypeError):
                controller.on_frame(raw, 250 * MS)
        self.assertEqual(controller.snapshot(), before)
        self.assertEqual(len(controller.events), count)


class ControllerClockAndSnapshotTests(unittest.TestCase):
    def test_constructor_rejects_non_uint32_tokens_and_non_integer_starts(self):
        for token in (-1, 0x100000000, True, False, 1.0, "1", None):
            with self.subTest(token=token), self.assertRaises(ValueError):
                DistanceTimeoutController(token, 0)
        for started_ns in (-1, True, False, 1.0, "1", None):
            with self.subTest(started_ns=started_ns), self.assertRaises(ValueError):
                DistanceTimeoutController(TOKEN, started_ns)
        for token in (0, 0xFFFFFFFF):
            self.assertEqual(DistanceTimeoutController(token, 0).run_token, token)

    def test_all_timestamp_methods_reject_bad_types_and_clock_regression(self):
        for method in ("poll", "arm", "on_frame"):
            controller = armed_controller()
            before, count = controller.snapshot(), len(controller.events)
            for stamp in (-1, 199 * MS, True, False, 1.0, "1", None):
                with self.subTest(method=method, stamp=stamp), self.assertRaises(ValueError):
                    if method == "on_frame":
                        controller.on_frame(distance_frame(), stamp)
                    else:
                        getattr(controller, method)(stamp)
            self.assertEqual(controller.snapshot(), before)
            self.assertEqual(len(controller.events), count)

    def test_poll_and_frame_share_one_monotonic_order(self):
        controller = armed_controller()
        controller.poll(250 * MS)
        with self.assertRaises(ValueError):
            controller.on_frame(distance_frame(), 249 * MS)
        controller.on_frame(distance_frame(), 250 * MS)
        controller.poll(250 * MS)
        self.assertEqual(controller.last_valid_rx_ns, 250 * MS)

    def test_first_operation_cannot_precede_started_time(self):
        controller = DistanceTimeoutController(TOKEN, 100)
        with self.assertRaises(ValueError):
            controller.poll(99)
        self.assertEqual(controller.snapshot()["last_clock_ns"], 100)

    def test_snapshot_is_detached_and_does_not_advance_time(self):
        controller = armed_controller()
        snapshot = controller.snapshot()
        snapshot["stop"] = True
        snapshot["last_valid_rx_ns"] = 0
        self.assertFalse(controller.stop)
        self.assertEqual(controller.last_valid_rx_ns, 200 * MS)
        self.assertEqual(controller.snapshot()["last_clock_ns"], 200 * MS)

    def test_transition_and_receive_events_preserve_host_clock_and_state(self):
        controller = armed_controller()
        event = controller.on_frame(distance_frame(distance=200, counter=5), 250 * MS)
        self.assertIs(event, controller.events[-2])
        transitions = [item for item in controller.events if item["event"] == "state_transition"]
        self.assertEqual([item["state"] for item in transitions],
                         [INIT_INHIBITED, ARMED, STOP_LATCHED])
        self.assertEqual([item["host_monotonic_ns"] for item in transitions], [0, 200 * MS, 250 * MS])
        self.assertEqual([item["host_monotonic_ns"] for item in controller.events],
                         sorted(item["host_monotonic_ns"] for item in controller.events))


if __name__ == "__main__":
    unittest.main()
