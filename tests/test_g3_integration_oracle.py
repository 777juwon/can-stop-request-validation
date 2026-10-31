"""독립 판정의 합성 로그 검사다. 실제 CAN/CARLA 또는 G3 성공 증거가 아니다."""

import copy
import struct
import unittest

from tools.g3_integration_oracle import evaluate_integration


TOKEN = 0x11223344
ACTOR = 77


def fixture(*, hold_start=4, step=0.05, prefix_speed=1.3):
    """송신기·core 코드를 호출하지 않고 검사용 관측 자료를 구성한다."""
    armed_ns = 2_001_000_000
    metadata = {
        "run_token": TOKEN, "actor_id": ACTOR, "coordinator_pid": 10,
        "worker_pids": {"sender": 11, "observer": 12},
        "preparation_started_monotonic_ns": 950_000_000,
        "preparation_deadline_monotonic_ns": 30_950_000_000,
        "preparation_completed_monotonic_ns": 2_000_500_000,
        "armed": {"host_monotonic_ns": armed_ns, "frame": 120, "simulation_time_s": 20 * step},
        "execution_status": "COMPLETE", "sender_exit_code": 0, "observer_exit_code": 0,
        "fixture_sends_complete": True, "observation_window_complete": True,
    }
    tx, observed, received, events, samples = [], [], [], [], []
    for slot in range(20):
        stop, reason = (1, 1) if 5 <= slot <= 9 else (0, 0)
        payload = bytes((stop, reason, slot, 0, 0x44, 0x33, 0x22, 0x11))
        raw = struct.pack("=IB3x8s", 0x200, 8, payload)
        fields = {"raw_frame_hex": raw.hex(), "arbitration_id": 0x200, "dlc": 8,
                  "data_hex": payload.hex(), "extended": False, "remote": False, "error_frame": False}
        due = armed_ns + 10_000_000 + slot * 50_000_000
        tx.append({"event": "tx", "slot": slot, "scheduled_ns": due,
                   "s_begin_ns": due, "s_done_ns": due + 3_000, "bytes_sent": 16, "pid": 11, **fields})
        # 다른 프로세스의 수신은 송신 호출 반환보다 먼저 관측될 수 있다.
        observed.append({"event": "rx", "pid": 12, "host_monotonic_ns": due + 1_000, **fields})
        received.append({"event": "rx", "pid": 10, "actor_id": ACTOR,
                         "host_monotonic_ns": due + 2_000, **fields})
        event = {"event": "request", "actor_id": ACTOR, "a_rx_ns": due + 2_000,
                 "raw_frame_hex": raw.hex(),
                 "request": {"stop": bool(stop), "reason": reason, "counter": slot, "run_token": TOKEN},
                 "action": "KEEP_EXISTING_CONTROL" if slot < 5 else "APPLY_FULL_BRAKE",
                 "stop_latched": slot >= 5, "first_reason": None if slot < 5 else 1}
        if slot >= 5:
            event.update(call_begin_ns=due + 3_000, a_done_ns=due + 4_000,
                         response={"actor_id": ACTOR, "error": "", "do_tick_cue": False},
                         call_completed=True, processing_duration_ns=2_000, call_within_50ms=True)
        events.append(event)

    def sample(frame, stamp, host, speed, phase, brake):
        return {"phase": phase, "frame": frame, "simulation_time_s": stamp, "simulation_delta_s": step,
                "host_monotonic_ns": host, "tick_begin_monotonic_ns": host - 2_000_000,
                "tick_done_monotonic_ns": host - 1_000_000, "actor_id": ACTOR,
                "velocity_mps": {"x": speed, "y": 0.0, "z": 0.0}, "speed_mps": speed,
                "applied_control": {"throttle": 0.0 if brake else 0.2, "brake": float(brake),
                                    "steer": 0.0, "hand_brake": False}, "transform": {}}
    for i in range(21):
        samples.append(sample(100 + i, i * step, 1_000_000_000 + i * 50_000_000,
                              5 / 3.6, "drive", 0))
    for i in range(46):
        speed = prefix_speed if i < 5 else 0.05 if i - 5 >= hold_start else 1.2
        samples.append(sample(121 + i, (21 + i) * step, armed_ns + (i + 1) * 50_000_000,
                              speed, "g3", i >= 5))
    return metadata, tx, observed, received, events, samples


class IntegrationOracleTests(unittest.TestCase):
    def test_complete_independent_evidence_passes(self):
        result = evaluate_integration(*fixture())
        self.assertTrue(result["all_checks_passed"], result)
        self.assertEqual(result["metrics"]["stop_hold"]["sample_count"], 11)
        self.assertEqual(result["metrics"]["main_comparison_runs_executed"], 0)
        self.assertEqual(result["metrics"]["max_processing_ms"], 0.002)

    def test_complete_missing_observation_and_wrong_raw_cannot_pass(self):
        data = list(fixture())
        data[2].pop(7)
        self.assertEqual(evaluate_integration(*data)["transport_status"], "FAIL")
        data = list(fixture())
        wrong = bytes.fromhex(data[2][5]["raw_frame_hex"])
        wrong = wrong[:-4] + bytes.fromhex("88776655")
        data[2][5]["raw_frame_hex"] = wrong.hex()
        data[2][5]["data_hex"] = wrong[8:].hex()
        self.assertEqual(evaluate_integration(*data)["transport_status"], "FAIL")

    def test_counter_order_and_worker_independence_are_checked(self):
        for change in ("duplicate", "reorder", "same_pid", "metadata_pid"):
            data = list(fixture())
            if change == "duplicate":
                data[2][-1] = copy.deepcopy(data[2][-2])
            elif change == "reorder":
                data[2][4], data[2][5] = data[2][5], data[2][4]
            elif change == "same_pid":
                for row in data[2]:
                    row["pid"] = 11
            else:
                data[0]["worker_pids"]["observer"] = 99
            with self.subTest(change=change):
                self.assertFalse(evaluate_integration(*data)["all_checks_passed"])

    def test_internal_pass_labels_do_not_replace_observations(self):
        data = list(fixture())
        data[0].update(all_checks_passed=True, motion_status="PASS", transport_status="PASS")
        for row in data[4][5:]:
            row["call_within_50ms"] = True
        data[5] = []
        result = evaluate_integration(*data)
        self.assertFalse(result["all_checks_passed"])
        self.assertEqual(result["motion_status"], "FAIL")

    def test_call_fifty_millisecond_boundary_uses_actual_timestamps(self):
        for offset, expected in ((50_000_000, "PASS"), (50_000_001, "FAIL")):
            data = list(fixture())
            last = data[4][-1]
            last["a_done_ns"] = last["a_rx_ns"] + offset
            last["processing_duration_ns"] = 0
            last["call_within_50ms"] = True
            result = evaluate_integration(*data)
            with self.subTest(offset=offset):
                self.assertEqual(result["adapter_status"], expected, result)
        data = list(fixture())
        for row in data[4][5:]:
            row.update(processing_duration_ns=999_999_999, call_within_50ms=False)
        self.assertTrue(evaluate_integration(*data)["all_checks_passed"])

    def test_receive_must_match_raw_and_independent_receive_time(self):
        for field in ("time", "actor", "raw"):
            data = list(fixture())
            if field == "time":
                data[4][5]["a_rx_ns"] += 1
            elif field == "actor":
                data[3][5]["actor_id"] = 99
            else:
                data[3][5]["data_hex"] = "0000000000000000"
            with self.subTest(field=field):
                self.assertEqual(evaluate_integration(*data)["adapter_status"], "FAIL")

    def test_bad_response_or_released_latch_fails(self):
        for change in ("actor", "tick", "reason", "action"):
            data = list(fixture())
            event = data[4][10]
            if change == "actor":
                event["response"]["actor_id"] = 88
            elif change == "tick":
                event["response"]["do_tick_cue"] = True
            elif change == "reason":
                event["first_reason"] = 0
            else:
                event["action"] = "KEEP_EXISTING_CONTROL"
            with self.subTest(change=change):
                self.assertEqual(evaluate_integration(*data)["adapter_status"], "FAIL")

    def test_velocity_is_recalculated_from_actual_components(self):
        data = list(fixture())
        for row in data[5][:21]:
            row["velocity_mps"]["x"] = 0.0
        result = evaluate_integration(*data)
        self.assertEqual(result["motion_status"], "FAIL")
        self.assertFalse(result["metrics"]["actual_prefix_motion_observed"])

    def test_normal_prefix_does_not_need_an_extra_speed_band(self):
        self.assertTrue(evaluate_integration(*fixture(prefix_speed=0.2))["all_checks_passed"])

    def test_frame_and_simulation_time_continuity_are_required(self):
        for change in ("frame", "time", "actor"):
            data = list(fixture())
            if change == "frame":
                data[5].pop(33)
            elif change == "time":
                data[5][33]["simulation_time_s"] += 0.01
            else:
                data[5][33]["actor_id"] = 88
            with self.subTest(change=change):
                self.assertEqual(evaluate_integration(*data)["motion_status"], "FAIL")

    def test_float32_exact_two_second_window_includes_frame_forty(self):
        step = struct.unpack("<f", struct.pack("<f", 0.05))[0]
        result = evaluate_integration(*fixture(hold_start=30, step=step))
        self.assertTrue(result["all_checks_passed"], result)
        self.assertEqual(result["metrics"]["stop_hold_completed_after_applied_frames"], 40)
        self.assertEqual(evaluate_integration(*fixture(hold_start=31, step=step))["motion_status"], "FAIL")

    def test_preparation_deadline_and_latched_vehicle_brake_are_checked(self):
        for change in ("deadline", "brake"):
            data = list(fixture())
            if change == "deadline":
                data[0]["preparation_completed_monotonic_ns"] = data[0]["preparation_deadline_monotonic_ns"] + 1
            else:
                data[5][-1]["applied_control"]["brake"] = 0.0
            with self.subTest(change=change):
                self.assertEqual(evaluate_integration(*data)["motion_status"], "FAIL")

    def test_incomplete_missing_evidence_is_inconclusive(self):
        data = list(fixture())
        data[0].update(execution_status="INTERRUPTED", fixture_sends_complete=False,
                       observation_window_complete=False, sender_exit_code=-15, observer_exit_code=-15)
        data[1:5] = [rows[:3] for rows in data[1:5]]
        data[5] = data[5][:24]
        result = evaluate_integration(*data)
        self.assertFalse(result["all_checks_passed"])
        self.assertEqual(result["failures"], [])
        self.assertTrue(all(result[key] == "INCONCLUSIVE" for key in
                            ("transport_status", "adapter_status", "motion_status")), result)

    def test_later_normal_request_needs_a_subsequent_vehicle_observation(self):
        data = list(fixture())
        # 시뮬레이터가 빨리 전진해 2초 창이 끝나도 이후 정상 요청의 제동 근거가 필요하다.
        for i, row in enumerate(data[5][26:]):
            host = 2_301_000_000 + i * 5_000_000
            row.update(host_monotonic_ns=host, tick_begin_monotonic_ns=host - 2_000_000,
                       tick_done_monotonic_ns=host - 1_000_000)
        result = evaluate_integration(*data)
        self.assertEqual(result["transport_status"], "PASS")
        self.assertIn("state_after_last_brake_call_missing", [item["code"] for item in result["failures"]])

    def test_pre_request_ackermann_brake_is_not_can_application(self):
        data = list(fixture())
        data[5][21]["applied_control"].update(throttle=0.0, brake=1.0)
        result = evaluate_integration(*data)
        self.assertTrue(result["all_checks_passed"], result)
        self.assertEqual(result["metrics"]["first_brake_applied"]["frame"], 126)
        self.assertEqual(result["metrics"]["pre_request_full_brake_frames"], [121])
        for row in data[5][26:]:
            row["applied_control"]["brake"] = 0.0
        result = evaluate_integration(*data)
        self.assertEqual(result["motion_status"], "FAIL")
        self.assertIsNone(result["metrics"]["first_brake_applied"])

    def test_arm_must_refer_to_the_last_drive_snapshot(self):
        data = list(fixture())
        data[0]["armed"].update(frame=119, simulation_time_s=0.95)
        result = evaluate_integration(*data)
        self.assertIn("arm_not_last_drive_snapshot", [item["code"] for item in result["failures"]])

    def test_incomplete_run_preserves_observed_late_call_and_brake_failure(self):
        data = list(fixture())
        data[0].update(execution_status="ENV_ERROR", observation_window_complete=False)
        data[4][-1]["a_done_ns"] = data[4][-1]["a_rx_ns"] + 50_000_001
        data[5][-1]["applied_control"]["brake"] = 0.0
        result = evaluate_integration(*data)
        self.assertEqual(result["adapter_status"], "FAIL")
        self.assertEqual(result["motion_status"], "FAIL")
        self.assertIn("control_call_late", [item["code"] for item in result["failures"]])


if __name__ == "__main__":
    unittest.main()
