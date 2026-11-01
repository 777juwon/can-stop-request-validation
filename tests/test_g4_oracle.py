"""G4 독립 판정의 합성 로그 검사다. 실제 CAN/CARLA 실행 증거가 아니다."""

import copy
import struct
import unittest

from tools.g4_oracle import evaluate_g4


TOKEN = 0x11223344
ACTOR = 77
PERIOD = 50_000_000


def fixture(*, hold_start=4, step=0.05, timeout_delay_ns=0):
    """SUT와 fixture 생성기를 사용하지 않고 원시 관측 자료를 구성한다."""
    origin = 1_000_000_000
    arm = origin + 300_000_000
    t0 = origin + 256 * PERIOD
    end = t0 + 20_000_000_000
    metadata = {
        "run_token": TOKEN, "actor_id": ACTOR, "coordinator_pid": 10,
        "worker_pids": {"sender": 11, "observer": 12, "controller": 13},
        "worker_results": {role: {"status": "COMPLETE", "pid": pid, "run_token": TOKEN}
                           for role, pid in (("sender", 11), ("observer", 12), ("controller", 13))},
        "execution_status": "COMPLETE", "fixture_sends_complete": True,
        "observation_window_complete": True,
        "sender_exit_code": 0, "observer_exit_code": 0, "controller_exit_code": 0,
        "t0_ns": t0, "t0_done_ns": t0 + 3_000, "trial_global_slot": 256,
        "trial_first_scheduled_ns": t0, "trial_end_ns": end,
        "armed": {"host_monotonic_ns": arm}, "adapter_active_ns": arm + 5_000,
        "preparation_started_monotonic_ns": origin - 10_000_000,
        "preparation_deadline_monotonic_ns": origin - 10_000_000 + 30_000_000_000,
        "preparation_completed_monotonic_ns": t0 - 40_000_000,
    }
    inputs, observed, sut, received, events, samples = [], [], [], [], [], []

    def raw_fields(can_id, payload):
        raw = struct.pack("=IB3x8s", can_id, 8, payload)
        return {"raw_frame_hex": raw.hex(), "arbitration_id": can_id, "dlc": 8,
                "data_hex": payload.hex(), "extended": False, "remote": False, "error_frame": False}

    for global_slot in range(656):
        slot = global_slot - 256
        due = origin + global_slot * PERIOD
        for can_id in (0x100, 0x101):
            if can_id == 0x100 and 100 <= slot <= 159:
                continue
            payload = ((b"\xe8\x03" + bytes((global_slot % 256, 1))) if can_id == 0x100
                       else bytes((global_slot % 256, 0, 0, 0))) + TOKEN.to_bytes(4, "little")
            fields = raw_fields(can_id, payload)
            inputs.append({"event": "tx", "phase": "prepare" if slot < 0 else "trial",
                           "slot": None if slot < 0 else slot, "global_slot": global_slot,
                           "scheduled_ns": due, "s_begin_ns": due, "s_done_ns": due + 3_000,
                           "bytes_sent": 16, "pid": 11, **fields})
            observed.append({"event": "rx", "pid": 12, "host_monotonic_ns": due + 1_000, **fields})

    first_timeout_at = t0 + 5_150_000_000 + timeout_delay_ns
    for index in range(657):
        due = origin + index * PERIOD
        stop, reason = (1, 4) if due < arm else (0, 0) if due < first_timeout_at else (1, 2)
        payload = bytes((stop, reason, index % 256, 0)) + TOKEN.to_bytes(4, "little")
        fields = raw_fields(0x200, payload)
        sut.append({"event": "request_tx", "pid": 13, "s_begin_ns": due,
                    "s_done_ns": due + 3_000, "bytes_sent": 16, **fields})
        observed.append({"event": "rx", "pid": 12, "host_monotonic_ns": due + 1_000, **fields})
        if due < metadata["adapter_active_ns"]:
            continue
        received.append({"event": "rx", "pid": 10, "actor_id": ACTOR,
                         "host_monotonic_ns": due + 2_000, **fields})
        latched = due >= first_timeout_at
        event = {"event": "request", "actor_id": ACTOR, "a_rx_ns": due + 2_000,
                 "raw_frame_hex": fields["raw_frame_hex"],
                 "request": {"stop": bool(stop), "reason": reason, "counter": index % 256, "run_token": TOKEN},
                 "action": "APPLY_FULL_BRAKE" if latched else "KEEP_EXISTING_CONTROL",
                 "stop_latched": latched, "first_reason": 2 if latched else None}
        if latched:
            event.update(call_begin_ns=due + 3_000, a_done_ns=due + 4_000,
                         response={"actor_id": ACTOR, "error": "", "do_tick_cue": False},
                         call_completed=True, processing_duration_ns=2_000, call_within_50ms=True)
        events.append(event)
    observed.sort(key=lambda row: row["host_monotonic_ns"])

    def sample(frame, host, speed, phase, brake):
        return {"phase": phase, "frame": frame, "simulation_time_s": (frame - 100) * step,
                "simulation_delta_s": step, "host_monotonic_ns": host,
                "tick_begin_monotonic_ns": host - 2_000_000,
                "tick_done_monotonic_ns": host - 1_000_000, "actor_id": ACTOR,
                "velocity_mps": {"x": speed, "y": 0.0, "z": 0.0}, "speed_mps": speed,
                "applied_control": {"throttle": 0.0 if brake else 0.2, "brake": float(brake),
                                    "steer": 0.0, "hand_brake": False}}

    frame = 100
    for host in range(arm + PERIOD, t0, PERIOD):
        samples.append(sample(frame, host, 5 / 3.6, "drive", False))
        frame += 1
    metadata["trial_ready"] = {key: samples[-1][key] for key in ("frame", "simulation_time_s", "host_monotonic_ns")}
    first_applied_at = first_timeout_at + PERIOD
    for host in range(t0 + PERIOD, end + 2 * PERIOD, PERIOD):
        braking = host >= first_applied_at
        speed = 0.05 if host >= first_applied_at + hold_start * PERIOD else 5 / 3.6
        samples.append(sample(frame, host, speed, "g4", braking))
        frame += 1
    return metadata, inputs, observed, sut, received, events, samples


class G4OracleTests(unittest.TestCase):
    def assert_failed(self, data, domain, code=None):
        """변경한 증거가 해당 영역에서 실제 실패하는지 확인한다."""
        result = evaluate_g4(*data)
        self.assertFalse(result["all_checks_passed"], result)
        self.assertEqual(result[domain + "_status"], "FAIL", result)
        if code:
            self.assertIn(code, [row["code"] for row in result["failures"]], result)
        return result

    def test_complete_independent_evidence_passes(self):
        result = evaluate_g4(*fixture())
        self.assertTrue(result["all_checks_passed"], result)
        self.assertEqual(result["metrics"]["main_comparison_runs_executed"], 0)
        self.assertEqual(result["metrics"]["stop_hold"]["sample_count"], 11)
        self.assertEqual(result["metrics"]["max_processing_ms"], 0.002)
        self.assertGreaterEqual(result["metrics"]["normal_distance_frames_before_arm"], 5)

    def test_interruption_omits_only_sixty_distance_slots(self):
        data = list(fixture())
        row = copy.deepcopy(next(row for row in data[1] if row["phase"] == "trial" and row["slot"] == 100))
        row.update(arbitration_id=0x100)
        raw = struct.pack("=IB3x8s", 0x100, 8, b"\xe8\x03\x64\x01" + TOKEN.to_bytes(4, "little"))
        row.update(raw_frame_hex=raw.hex(), data_hex=raw[8:].hex())
        data[1].append(row)
        self.assert_failed(data, "transport", "distance_sent_during_interruption")

    def test_background_and_restored_distance_are_required(self):
        for can_id, slot in ((0x101, 120), (0x100, 160)):
            data = list(fixture())
            data[1] = [row for row in data[1] if not (row["arbitration_id"] == can_id and row["slot"] == slot)]
            with self.subTest(can_id=can_id):
                self.assert_failed(data, "transport", "trial_fixture_incomplete")

    def test_raw_bytes_override_decoded_and_internal_verdicts(self):
        data = list(fixture())
        data[0]["all_checks_passed"] = True
        row = data[2][0]
        row["raw_frame_hex"] = row["raw_frame_hex"][:-2] + "ff"
        self.assert_failed(data, "transport", "raw_run_token_mismatch")
        data = list(fixture())
        data[2][0]["extended"] = True
        self.assert_failed(data, "transport", "raw_decoded_disagreement")

    def test_four_process_identities_and_row_pids_are_required(self):
        for change in ("worker", "row", "controller"):
            data = list(fixture())
            if change == "worker":
                data[0]["worker_pids"]["controller"] = 11
            elif change == "row":
                data[2][0]["pid"] = 10
            else:
                data[3][0]["pid"] = 11
            with self.subTest(change=change):
                self.assert_failed(data, "request" if change == "controller" else "transport")

    def test_actual_t0_and_global_counter_are_required(self):
        for change in ("t0", "counter", "scheduled"):
            data = list(fixture())
            if change == "t0":
                data[0]["t0_ns"] += 1
            elif change == "counter":
                data[0]["trial_global_slot"] = 255
            else:
                next(row for row in data[1] if row["slot"] == 20)["scheduled_ns"] += 1
            with self.subTest(change=change):
                self.assert_failed(data, "transport")

    def test_five_normal_raw_inputs_must_precede_arm(self):
        data = list(fixture())
        data[0]["armed"]["host_monotonic_ns"] = 1_100_000_000
        self.assert_failed(data, "request", "five_independent_normal_inputs_before_arm_missing")

    def test_init_inhibited_before_arm_is_not_trial_stop(self):
        data = fixture()
        result = evaluate_g4(*data)
        self.assertTrue(result["all_checks_passed"], result)
        self.assertGreater(result["metrics"]["first_timeout_q_obs_ns"], data[0]["t0_ns"])

    def test_timeout_window_uses_last_ninety_nine_send_edges(self):
        base = list(fixture())
        row = next(row for row in base[2] if row["arbitration_id"] == 0x200 and row["data_hex"].startswith("0102"))
        due = next(row for row in base[1] if row["arbitration_id"] == 0x100 and row["slot"] == 99)
        for stamp, code in ((due["s_begin_ns"] + 200_000_000 - 1, "timeout_request_before_200ms"),
                            (due["s_done_ns"] + 300_000_000 + 1, "timeout_request_after_300ms")):
            data = copy.deepcopy(base)
            target = next(item for item in data[2] if item["raw_frame_hex"] == row["raw_frame_hex"]
                          and item["host_monotonic_ns"] == row["host_monotonic_ns"])
            target["host_monotonic_ns"] = stamp
            with self.subTest(code=code):
                self.assert_failed(data, "request", code)

    def test_exact_timeout_observation_boundaries_are_inclusive(self):
        for delay in (0, 100_000_000):
            data = list(fixture(timeout_delay_ns=delay))
            last = next(row for row in data[1] if row["arbitration_id"] == 0x100 and row["slot"] == 99)
            first = next(row for row in data[2] if row["arbitration_id"] == 0x200
                         and row["data_hex"].startswith("0102"))
            first["host_monotonic_ns"] = (last["s_begin_ns"] + 200_000_000 if delay == 0
                                           else last["s_done_ns"] + 300_000_000)
            data[2].sort(key=lambda row: row["host_monotonic_ns"])
            result = evaluate_g4(*data)
            with self.subTest(delay=delay):
                self.assertTrue(result["all_checks_passed"], result)

    def test_request_must_match_controller_and_remain_latched(self):
        data = list(fixture())
        data[3].pop(400)
        self.assert_failed(data, "request", "independent_request_observation_without_matching_source")
        data = list(fixture())
        source = data[3][-2]
        original = source["raw_frame_hex"]
        raw = bytearray.fromhex(original)
        raw[8:10] = b"\x00\x00"
        source.update(raw_frame_hex=raw.hex(), data_hex=raw[8:].hex())
        seen = next(row for row in data[2] if row["raw_frame_hex"] == original
                    and row["host_monotonic_ns"] >= data[0]["t0_ns"] + 8_000_000_000)
        seen.update(raw_frame_hex=raw.hex(), data_hex=raw[8:].hex())
        self.assert_failed(data, "request", "stop_request_released_after_timeout")

    def test_r06_uses_actual_fifty_millisecond_boundary(self):
        for offset, expected in ((50_000_000, "PASS"), (50_000_001, "FAIL")):
            data = list(fixture())
            event = next(row for row in data[5] if row.get("call_completed"))
            event.update(a_done_ns=event["a_rx_ns"] + offset,
                         processing_duration_ns=0, call_within_50ms=True)
            result = evaluate_g4(*data)
            with self.subTest(offset=offset):
                self.assertEqual(result["adapter_status"], expected, result)

    def test_adapter_receive_event_and_actor_match(self):
        for change in ("time", "actor", "request", "reason", "response"):
            data = list(fixture())
            event = next(row for row in data[5] if row.get("call_completed"))
            if change == "time":
                event["a_rx_ns"] += 1
            elif change == "actor":
                event["actor_id"] = 88
            elif change == "request":
                event["request"]["reason"] = 4
            elif change == "reason":
                event["first_reason"] = 4
            else:
                event["response"]["do_tick_cue"] = True
            with self.subTest(change=change):
                self.assert_failed(data, "adapter")

    def test_motion_uses_components_and_requires_continuous_frames(self):
        for change in ("speed", "frame", "time", "actor", "control"):
            data = list(fixture())
            sample = data[6][-10]
            if change == "speed":
                sample["velocity_mps"]["x"] = 5.0
            elif change == "frame":
                data[6].pop(-10)
            elif change == "time":
                sample["simulation_time_s"] += 0.01
            elif change == "actor":
                sample["actor_id"] = 88
            else:
                sample["applied_control"]["brake"] = 0.0
            with self.subTest(change=change):
                self.assert_failed(data, "motion")

    def test_stop_hold_ends_within_frame_forty_even_with_float32_step(self):
        step = struct.unpack("<f", struct.pack("<f", 0.05))[0]
        result = evaluate_g4(*fixture(hold_start=30, step=step))
        self.assertTrue(result["all_checks_passed"], result)
        self.assertEqual(result["metrics"]["stop_hold_completed_after_applied_frames"], 40)
        self.assert_failed(fixture(hold_start=31, step=step), "motion", "stop_hold_not_observed_within_40_frames")

    def test_pre_request_ackermann_brake_does_not_anchor_motion(self):
        data = list(fixture())
        first = next(row for row in data[6] if row["phase"] == "g4")
        first["applied_control"].update(throttle=0.0, brake=1.0)
        result = evaluate_g4(*data)
        self.assertTrue(result["all_checks_passed"], result)
        self.assertEqual(result["metrics"]["pre_request_full_brake_frames"], [first["frame"]])
        self.assertGreater(result["metrics"]["first_brake_applied"]["frame"], first["frame"])

    def test_speed_preparation_deadline_ready_and_tail_are_checked(self):
        for change in ("deadline", "ready", "speed", "tail"):
            data = list(fixture())
            if change == "deadline":
                data[0]["preparation_deadline_monotonic_ns"] = data[0]["t0_ns"] - 1
            elif change == "ready":
                data[0]["trial_ready"]["frame"] -= 1
            elif change == "speed":
                for row in data[6]:
                    if row["phase"] == "drive":
                        row["speed_mps"] = row["velocity_mps"]["x"] = 0.0
            else:
                row = next(row for row in reversed(data[6]) if row["phase"] == "drive")
                row["speed_mps"] = row["velocity_mps"]["x"] = 0.0
            with self.subTest(change=change):
                self.assert_failed(data, "motion")

    def test_complete_missing_logs_and_worker_errors_fail(self):
        for index, domain in ((1, "transport"), (2, "transport"), (3, "request"),
                              (4, "adapter"), (5, "adapter"), (6, "motion")):
            data = list(fixture())
            data[index] = []
            with self.subTest(index=index):
                self.assert_failed(data, domain)
        data = list(fixture())
        data[0]["controller_exit_code"] = 2
        self.assert_failed(data, "request", "worker_exit_not_successful")

    def test_worker_complete_records_must_match_actual_pids_and_token(self):
        for change in ("missing", "status", "pid", "token"):
            data = list(fixture())
            record = data[0]["worker_results"]["controller"]
            if change == "missing":
                del data[0]["worker_results"]["controller"]
            elif change == "status":
                record["status"] = "ENV_ERROR"
            elif change == "pid":
                record["pid"] = 11
            else:
                record["run_token"] = 1
            with self.subTest(change=change):
                self.assert_failed(data, "request")

    def test_interrupted_short_prefix_is_inconclusive(self):
        data = list(fixture())
        data[0].update(execution_status="INTERRUPTED", fixture_sends_complete=False,
                       observation_window_complete=False, sender_exit_code=-15,
                       observer_exit_code=-15, controller_exit_code=-15)
        data[1] = data[1][:4]
        data[2] = data[2][:6]
        data[3] = data[3][:2]
        data[4:7] = [[], [], []]
        result = evaluate_g4(*data)
        self.assertFalse(result["all_checks_passed"], result)
        self.assertEqual(result["failures"], [], result)
        self.assertTrue(all(result[domain + "_status"] == "INCONCLUSIVE"
                            for domain in ("transport", "request", "adapter", "motion")), result)

    def test_observed_failure_survives_environment_error(self):
        data = list(fixture())
        data[0].update(execution_status="ENV_ERROR", fixture_sends_complete=False,
                       observation_window_complete=False)
        data[2][0]["remote"] = True
        self.assert_failed(data, "transport", "raw_decoded_disagreement")

    def test_missing_arm_metadata_does_not_turn_init_into_proved_failure(self):
        data = list(fixture())
        data[0].update(execution_status="ENV_ERROR", fixture_sends_complete=False,
                       observation_window_complete=False)
        for key in ("armed", "actor_id", "t0_ns", "t0_done_ns", "run_token"):
            data[0].pop(key)
        result = evaluate_g4(*data)
        self.assertEqual(result["failures"], [], result)
        self.assertFalse(result["all_checks_passed"])

    def test_first_tick_after_actual_call_must_show_applied_brake(self):
        data = list(fixture())
        first = next(row for row in data[6] if row["phase"] == "g4" and row["applied_control"]["brake"])
        first["applied_control"].update(throttle=0.2, brake=0.0)
        self.assert_failed(data, "motion", "first_tick_after_brake_call_not_braking")

    def test_requests_and_vehicle_evidence_must_reach_run_end(self):
        data = list(fixture())
        cutoff = data[0]["t0_ns"] + 9_000_000_000
        data[3] = [row for row in data[3] if row["s_begin_ns"] < cutoff]
        data[2] = [row for row in data[2] if row["arbitration_id"] != 0x200 or row["host_monotonic_ns"] < cutoff]
        data[4] = [row for row in data[4] if row["host_monotonic_ns"] < cutoff]
        data[5] = [row for row in data[5] if row["a_rx_ns"] < cutoff]
        self.assert_failed(data, "request", "request_run_end_observation_missing")
        data = list(fixture())
        data[6] = [row for row in data[6] if row["host_monotonic_ns"] < data[0]["trial_end_ns"]]
        self.assert_failed(data, "motion", "vehicle_run_end_observation_missing")


if __name__ == "__main__":
    unittest.main()
