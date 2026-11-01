"""B 순번 감시의 가짜 시각 검사다. 실제 시간 성능이나 CAN 실행은 아니다."""

import unittest

from tests.test_g4_controller_core import MS, TOKEN, distance_frame
from tools.g4_controller_core import DistanceTimeoutController, G4ArmError
from tools.sequence_controller_core import SequenceProgressController


def armed(kind=SequenceProgressController):
    core = kind(TOKEN, 0)
    for counter in range(5):
        core.on_frame(distance_frame(counter=counter), counter * 50 * MS)
    core.arm(200 * MS)
    return core


class SequenceTests(unittest.TestCase):
    def test_advancing_same_distance_and_wrap_are_normal(self):
        core = SequenceProgressController(TOKEN, 0)
        for i, counter in enumerate((252, 253, 254, 255, 0)):
            self.assertTrue(core.on_frame(distance_frame(counter=counter), i * 50 * MS)["accepted"])
        core.arm(200 * MS)
        self.assertFalse(core.stop)
        self.assertEqual(core.last_counter, 0)

    def test_progress_delta_boundaries_and_rejected_near_values(self):
        for delta, accepted in ((0, False), (1, True), (127, True), (128, False), (255, False)):
            core = armed()
            event = core.on_frame(distance_frame(distance=100, counter=(4 + delta) % 256), 250 * MS)
            self.assertEqual(event["accepted"], accepted)
            self.assertEqual(core.last_counter, (4 + delta) % 256 if accepted else 4)
            self.assertEqual(core.distance_cm, 100 if accepted else 1000)
            self.assertEqual(core.last_valid_rx_ns, 250 * MS)
            self.assertEqual(core.last_progress_rx_ns, (250 if accepted else 200) * MS)
            self.assertEqual(core.stop, accepted)

    def test_repeat_keeps_rx_alive_but_expires_progress_at_exact_200ms(self):
        core = armed()
        for stamp in (250, 300, 350, 399):
            core.on_frame(distance_frame(counter=4), stamp * MS)
        self.assertFalse(core.stop)
        core.poll(400 * MS)
        self.assertEqual(core.reason, 3)
        self.assertTrue(core.stop)

    def test_a_b_difference_is_preserved_instead_of_forcing_both_to_stop(self):
        for kind, stopped in ((DistanceTimeoutController, False), (SequenceProgressController, True)):
            core = armed(kind)
            for stamp in (250, 300, 350, 400):
                core.on_frame(distance_frame(counter=4), stamp * MS)
            self.assertEqual(core.stop, stopped)

    def test_timeout_precedes_no_progress_when_both_expire(self):
        core = armed()
        core.poll(399 * MS)
        self.assertFalse(core.stop)
        core.poll(400 * MS)
        self.assertEqual(core.reason, 2)

    def test_heartbeat_and_invalid_input_refresh_neither_clock(self):
        for kwargs in ({"can_id": 0x101}, {"valid": 0}, {"token": TOKEN + 1},
                       {"distance": 10001}, {"can_id": 0x80000100}, {"dlc": 7}):
            core = armed()
            core.on_frame(distance_frame(**kwargs), 350 * MS)
            self.assertEqual((core.last_valid_rx_ns, core.last_progress_rx_ns), (200 * MS, 200 * MS))
            core.poll(400 * MS)
            self.assertEqual(core.reason, 2)

    def test_rejected_reference_is_kept_and_restoration_delta61_is_forward(self):
        core = armed()
        core.on_frame(distance_frame(counter=3), 250 * MS)
        self.assertEqual(core.last_counter, 4)
        core.on_frame(distance_frame(counter=65), 300 * MS)
        self.assertEqual(core.last_counter, 65)

    def test_restore_cannot_clear_first_reason_or_rearm(self):
        core = armed()
        for stamp in (250, 300, 350, 400):
            core.on_frame(distance_frame(counter=4), stamp * MS)
        core.on_frame(distance_frame(counter=65), 450 * MS)
        self.assertEqual((core.stop, core.reason), (True, 3))
        with self.assertRaises(G4ArmError):
            core.arm(450 * MS)

    def test_stale_progress_cannot_arm_despite_fresh_repeats(self):
        core = SequenceProgressController(TOKEN, 0)
        for counter in range(5):
            core.on_frame(distance_frame(counter=counter), counter * 50 * MS)
        for stamp in (250, 300, 350, 400):
            core.on_frame(distance_frame(counter=4), stamp * MS)
        with self.assertRaises(G4ArmError):
            core.arm(400 * MS)

    def test_repeated_startup_frame_does_not_create_five_new_inputs(self):
        core = SequenceProgressController(TOKEN, 0)
        for i in range(5):
            core.on_frame(distance_frame(counter=0), i * 50 * MS)
        self.assertEqual(core.valid_normal_count, 1)
        with self.assertRaises(G4ArmError):
            core.arm(200 * MS)

    def test_late_restoration_does_not_hide_prior_timeout(self):
        core = armed()
        core.on_frame(distance_frame(counter=5), 400 * MS)
        self.assertEqual(core.reason, 2)

    def test_invalid_clock_is_rejected_without_clearing_latch(self):
        core = armed()
        for stamp in (True, -1, 100 * MS):
            with self.assertRaises(ValueError):
                core.poll(stamp)
        with self.assertRaises(TypeError):
            core.on_frame(None, 250 * MS)


if __name__ == "__main__":
    unittest.main()
