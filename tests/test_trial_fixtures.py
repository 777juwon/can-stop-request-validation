"""네 고정 입력의 독립 바이트 예시와 경계 검증이다."""

import struct
import unittest

from tools.g4_can_workers import fixture_frames


class TrialFixturesTests(unittest.TestCase):
    def distance(self, scenario, slot):
        packet = fixture_frames(0x12345678, 256 + slot, slot, scenario)
        data = [raw[8:] for raw in packet if int.from_bytes(raw[:4], "little") == 0x100]
        return data[0] if data else None

    def test_all_scenario_frame_counts(self):
        for scenario, expected in (("T-01", 800), ("T-02", 800), ("T-03", 740), ("T-04", 800)):
            self.assertEqual(sum(len(fixture_frames(1, 256 + n, n, scenario)) for n in range(400)), expected)

    def test_near_threshold_is_exactly_slot260(self):
        self.assertEqual(struct.unpack("<HBBI", self.distance("T-02", 259))[0], 205)
        self.assertEqual(self.distance("T-02", 260).hex(), "c800040178563412")
        self.assertEqual(struct.unpack("<HBBI", self.distance("T-02", 399))[0], 50)

    def test_repeat_freezes_all_eight_bytes_and_restores_delta61(self):
        original = self.distance("T-04", 99)
        self.assertEqual(original.hex(), "e803630178563412")
        for n in range(100, 160):
            self.assertEqual(self.distance("T-04", n), original)
            heartbeat = fixture_frames(0x12345678, 256 + n, n, "T-04")[-1][8:]
            self.assertEqual(heartbeat[0], n)
        self.assertEqual(self.distance("T-04", 160).hex(), "e803a00178563412")

    def test_interruption_is_only_distance_and_only_sixty_slots(self):
        self.assertIsNotNone(self.distance("T-03", 99))
        self.assertIsNone(self.distance("T-03", 100))
        self.assertIsNone(self.distance("T-03", 159))
        self.assertIsNotNone(self.distance("T-03", 160))

    def test_unknown_scenario_cannot_be_silently_used(self):
        with self.assertRaises(ValueError):
            fixture_frames(1, 256, 0, "T-05")


if __name__ == "__main__":
    unittest.main()
