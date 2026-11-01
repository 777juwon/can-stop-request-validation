"""설치된 cantools로 DBC와 고정 바이트를 교차 확인한다."""

from pathlib import Path
import unittest

import cantools


class DbcContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = cantools.database.load_file(
            str(Path(__file__).resolve().parents[1] / "config/stop_request_v1.dbc"), encoding="utf-8")

    def test_only_three_standard_classic_eight_byte_messages(self):
        self.assertEqual({message.frame_id for message in self.database.messages}, {0x100, 0x101, 0x200})
        self.assertTrue(all(message.length == 8 and not message.is_extended_frame for message in self.database.messages))

    def test_literal_distance_and_heartbeat(self):
        token = 0x12345678
        self.assertEqual(self.database.encode_message("DistanceInput", {
            "distance_cm": 1000, "counter": 99, "valid": 1, "run_token": token}).hex(), "e803630178563412")
        self.assertEqual(self.database.encode_message("BackgroundHeartbeat", {
            "counter": 160, "reserved": 0, "run_token": token}).hex(), "a000000078563412")

    def test_all_stop_reasons_and_unsigned_boundaries(self):
        for reason in range(5):
            values = {"stop": int(reason > 0), "reason": reason, "counter": 255, "reserved": 0, "run_token": 0xFFFFFFFF}
            data = self.database.encode_message("StopRequest", values)
            self.assertEqual(data, bytes((int(reason > 0), reason, 255, 0, 255, 255, 255, 255)))
            self.assertEqual(self.database.decode_message("StopRequest", data, decode_choices=False), values)


if __name__ == "__main__":
    unittest.main()
