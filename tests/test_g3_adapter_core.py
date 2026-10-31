"""adapter 핵심 동작의 단위 검사다. 실제 CAN/CARLA 실행 근거가 아니다."""

import struct
from types import SimpleNamespace
import unittest

from tools.g2_carla_smoke import apply_brake_control
from tools.g3_adapter_core import (
    AdapterCallError, BrakeAdapterCore, G3InputError, demo, parse_supported_request,
)


TOKEN = 0x12345678


def request_frame(stop=1, reason=1, counter=0, *, token=TOKEN, reserved=0, can_id=0x200, dlc=8):
    return struct.pack("=IB3x8s", can_id, dlc,
                       struct.pack("<BBBBI", stop, reason, counter, reserved, token))


def reply(**changes):
    return {"actor_id": 77, "error": "", "do_tick_cue": False, **changes}


class RequestParsingTests(unittest.TestCase):
    def test_known_raw_request(self):
        parsed = parse_supported_request(bytes.fromhex("00020000080000000101ab0078563412"), TOKEN)
        self.assertTrue(parsed.stop)
        self.assertEqual((parsed.reason, parsed.counter, parsed.run_token), (1, 0xAB, TOKEN))

    def test_supported_normal_and_stop_reasons(self):
        self.assertFalse(parse_supported_request(request_frame(0, 0), TOKEN).stop)
        for reason in (1, 2, 3, 4):
            self.assertEqual(parse_supported_request(request_frame(1, reason), TOKEN).reason, reason)

    def test_other_id_flags_length_and_dlc_are_outside_supported_input(self):
        frames = [request_frame(can_id=value) for value in (0x201, 0x80000200, 0x40000200, 0x20000200)]
        frames += [request_frame(dlc=7), bytes(72), bytes(15), bytearray(request_frame())]
        for raw in frames:
            with self.subTest(raw=raw), self.assertRaises(G3InputError):
                parse_supported_request(raw, TOKEN)

    def test_foreign_token_and_reserved_byte_are_reported(self):
        for raw in (request_frame(token=TOKEN + 1), request_frame(reserved=1)):
            with self.assertRaises(G3InputError):
                parse_supported_request(raw, TOKEN)

    def test_unassigned_combinations_are_outside_this_g3_domain(self):
        for stop, reason in ((2, 1), (1, 255), (0, 1), (1, 0)):
            with self.subTest(stop=stop, reason=reason), self.assertRaises(G3InputError):
                parse_supported_request(request_frame(stop, reason), TOKEN)

    def test_invalid_token_configuration_rejected(self):
        for token in (-1, 0x100000000, True, "1"):
            with self.subTest(token=token), self.assertRaises(ValueError):
                parse_supported_request(request_frame(), token)


class AdapterBehaviorTests(unittest.TestCase):
    def test_normal_request_keeps_control_without_acceleration_or_brake(self):
        calls = []
        adapter = BrakeAdapterCore(actor_id=77, run_token=TOKEN, apply_brake=lambda: calls.append(1))
        event = adapter.on_frame(request_frame(0, 0))
        self.assertEqual(calls, [])
        self.assertFalse(adapter.stop_latched)
        self.assertEqual(event["action"], "KEEP_EXISTING_CONTROL")
        self.assertNotIn("a_done_ns", event)

    def test_stop_remains_latched_after_normal_input_and_keeps_first_reason(self):
        calls = []
        def brake():
            calls.append("brake")
            return reply()

        adapter = BrakeAdapterCore(actor_id=77, run_token=TOKEN, apply_brake=brake)
        for stop, reason in ((1, 1), (1, 2), (0, 0)):
            event = adapter.on_frame(request_frame(stop, reason))
            self.assertTrue(event["stop_latched"])
            self.assertEqual(event["first_reason"], 1)
            self.assertEqual(event["action"], "APPLY_FULL_BRAKE")
        self.assertEqual(calls, ["brake"] * 3)

    def test_counter_is_recorded_without_adding_sequence_watchdog(self):
        adapter = BrakeAdapterCore(actor_id=77, run_token=TOKEN, apply_brake=reply)
        for counter in (255, 0, 0, 200, 1):
            event = adapter.on_frame(request_frame(counter=counter))
            self.assertEqual(event["request"]["counter"], counter)
            self.assertTrue(event["call_completed"])

    def test_unsupported_input_records_error_and_never_calls_brake(self):
        calls = []
        adapter = BrakeAdapterCore(actor_id=77, run_token=TOKEN, apply_brake=lambda: calls.append(1))
        with self.assertRaises(G3InputError):
            adapter.on_frame(request_frame(token=TOKEN + 1))
        self.assertEqual(calls, [])
        self.assertEqual(adapter.events[-1]["action"], "UNSUPPORTED_INPUT")
        self.assertIn("error", adapter.events[-1])
        with self.assertRaises(AdapterCallError):
            adapter.on_frame(request_frame())

    def test_callback_exception_preserves_latch_and_prevents_automatic_retry(self):
        calls = []
        def broken():
            calls.append(1)
            raise RuntimeError("RPC 실패")

        adapter = BrakeAdapterCore(actor_id=77, run_token=TOKEN, apply_brake=broken)
        with self.assertRaises(AdapterCallError):
            adapter.on_frame(request_frame())
        self.assertTrue(adapter.stop_latched)
        self.assertTrue(adapter.faulted)
        self.assertFalse(adapter.events[-1]["call_completed"])
        self.assertIn("RPC 실패", adapter.events[-1]["error"])
        with self.assertRaises(AdapterCallError):
            adapter.on_frame(request_frame(0, 0))
        self.assertEqual(calls, [1])

    def test_wrong_actor_error_or_extra_tick_response_fails(self):
        for value in (reply(actor_id=99), reply(error="실패"), reply(do_tick_cue=True), None):
            adapter = BrakeAdapterCore(actor_id=77, run_token=TOKEN, apply_brake=lambda: value)
            with self.subTest(response=value), self.assertRaises(AdapterCallError):
                adapter.on_frame(request_frame())
            self.assertTrue(adapter.faulted)

    def test_user_interrupt_is_preserved_and_adapter_cannot_resume(self):
        def interrupted():
            raise KeyboardInterrupt("사용자 취소")

        adapter = BrakeAdapterCore(actor_id=77, run_token=TOKEN, apply_brake=interrupted)
        with self.assertRaises(KeyboardInterrupt):
            adapter.on_frame(request_frame())
        self.assertTrue(adapter.faulted)
        self.assertTrue(adapter.stop_latched)
        self.assertTrue(adapter.events[-1]["interrupted"])
        with self.assertRaises(AdapterCallError):
            adapter.on_frame(request_frame(0, 0))

    def test_real_g2_brake_helper_can_be_connected_as_callback(self):
        calls = []
        def batch(commands, tick):
            calls.append((commands, tick))
            return [SimpleNamespace(actor_id=77, error="")]

        carla = SimpleNamespace(VehicleControl=lambda **kwargs: kwargs,
                                command=SimpleNamespace(ApplyVehicleControl=lambda actor_id, control: (actor_id, control)))
        client = SimpleNamespace(apply_batch_sync=batch)
        actor = SimpleNamespace(id=77)
        adapter = BrakeAdapterCore(actor_id=77, run_token=TOKEN,
                                   apply_brake=lambda: apply_brake_control(client, actor, carla))
        event = adapter.on_frame(request_frame())
        self.assertTrue(event["call_completed"])
        self.assertEqual(calls, [([(77, {"throttle": 0.0, "brake": 1.0, "steer": 0.0,
                                        "hand_brake": False})], False)])


class AdapterTimingTests(unittest.TestCase):
    def test_receive_to_completion_boundary_includes_processing_time(self):
        for duration, timely in ((50_000_000, True), (50_000_001, False)):
            times = iter((1_000_000_000 + 10_000_000, 1_000_000_000 + duration))
            adapter = BrakeAdapterCore(actor_id=77, run_token=TOKEN, apply_brake=reply,
                                       clock=lambda: next(times))
            event = adapter.on_frame(request_frame(), received_ns=1_000_000_000)
            self.assertEqual(event["processing_duration_ns"], duration)
            self.assertEqual(event["call_within_50ms"], timely)
            self.assertTrue(event["call_completed"])
            self.assertFalse(adapter.faulted)

    def test_clock_regression_is_not_a_negative_successful_duration(self):
        for times in ((999, 1001), (1001, 1000)):
            clock = iter(times)
            adapter = BrakeAdapterCore(actor_id=77, run_token=TOKEN, apply_brake=reply,
                                       clock=lambda: next(clock))
            with self.subTest(times=times), self.assertRaises(AdapterCallError):
                adapter.on_frame(request_frame(), received_ns=1000)
            self.assertTrue(adapter.faulted)

    def test_invalid_actor_or_received_timestamp_rejected(self):
        for actor_id in (0, -1, True, "77"):
            with self.assertRaises(ValueError):
                BrakeAdapterCore(actor_id=actor_id, run_token=TOKEN, apply_brake=reply)
        adapter = BrakeAdapterCore(actor_id=77, run_token=TOKEN, apply_brake=reply)
        for stamp in (-1, True, 1.0):
            with self.assertRaises(ValueError):
                adapter.on_frame(request_frame(), received_ns=stamp)


class AdapterLearningDemoTests(unittest.TestCase):
    def test_demo_is_explicitly_without_real_can_and_carla(self):
        result = demo()
        self.assertFalse(result["actual_can"])
        self.assertFalse(result["carla_executed"])
        self.assertEqual(result["brake_callback_count"], 2)
        self.assertEqual([e["action"] for e in result["events"]],
                         ["KEEP_EXISTING_CONTROL", "APPLY_FULL_BRAKE", "APPLY_FULL_BRAKE"])


if __name__ == "__main__":
    unittest.main()
