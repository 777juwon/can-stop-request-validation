"""본시험 판정의 합성 로그 검사다. 실제 CARLA 실행 근거가 아니다."""

import math
import struct
import unittest

from tests.test_message_trial_oracle import fixture as message_fixture
from tools.main_plan import ROOT, canonical, digest, load_config
from tools.main_trial_oracle import evaluate_main_trial


def fixture(variant="A", scenario="T-03", step=.05):
    meta, inputs, observed, sut = message_fixture(variant, scenario)
    config = load_config()
    import json
    reference = json.loads((ROOT / config["physics_reference"]).read_text())
    meta.update(actor_id=77, fixed_config=config, config_sha256=digest(canonical(config)),
                client_version="0.9.15", server_version="0.9.15", map="Carla/Maps/Town04",
                vehicle_blueprint="vehicle.tesla.model3", spawn_index=143,
                spawn_transform=config["spawn_transform"], vehicle_physics=reference["vehicle_physics"],
                physics_normalized_sha256=config["physics_normalized_sha256"],
                ackermann_controller_settings=config["ackermann_settings"],
                corridor={"lane_width_m": 3.5}, adapter_active_ns=meta["armed"]["host_monotonic_ns"] + 500_000)
    received, events = [], []
    meta["adapter_prearm_rx"] = []
    latched, reason = False, None
    for source in sut:
        stamp = source["s_begin_ns"]
        if stamp < meta["adapter_active_ns"]:
            meta["adapter_prearm_rx"].append({**source, "event": "rx", "pid": 10, "actor_id": 77,
                                             "host_monotonic_ns": stamp + 3000})
            continue
        raw = bytes.fromhex(source["raw_frame_hex"])
        stop, why, counter = raw[8:11]
        if stop and not latched:
            latched, reason = True, why
        rx = {**source, "event": "rx", "pid": 10, "actor_id": 77, "host_monotonic_ns": stamp + 3000}
        event = {"event": "request", "actor_id": 77, "raw_frame_hex": source["raw_frame_hex"],
                 "a_rx_ns": stamp + 3000, "request": {"stop": bool(stop), "reason": why, "counter": counter, "run_token": meta["run_token"]},
                 "stop_latched": latched, "first_reason": reason,
                 "action": "APPLY_FULL_BRAKE" if latched else "KEEP_EXISTING_CONTROL"}
        if latched:
            event.update(call_begin_ns=stamp + 4000, a_done_ns=stamp + 5000, call_completed=True,
                         response={"actor_id": 77, "error": "", "do_tick_cue": False})
        received.append(rx)
        events.append(event)
    first_done = next((event["a_done_ns"] for event in events if "a_done_ns" in event), None)
    origin, t0 = config["spawn_transform"], meta["t0_ns"]
    yaw = math.radians(origin["yaw"])

    def sample(frame, sim, host, phase, speed, brake, distance=5):
        return {"frame": frame, "simulation_time_s": sim, "simulation_delta_s": step,
                "host_monotonic_ns": host, "tick_begin_monotonic_ns": host - 2_000_000,
                "tick_done_monotonic_ns": host - 1_000_000, "phase": phase, "actor_id": 77,
                "speed_mps": speed, "velocity_mps": {"x": speed * math.cos(yaw), "y": speed * math.sin(yaw), "z": 0},
                "applied_control": {"brake": float(brake), "throttle": 0. if brake else .2, "steer": 0., "hand_brake": False},
                "transform": {"x": origin["x"] + distance * math.cos(yaw), "y": origin["y"] + distance * math.sin(yaw), "z": origin["z"]}}

    samples = [sample(100 + i, i * step, t0 - (20 - i) * 50_000_000 - 10_000_000, "drive", 5 / 3.6, False)
               for i in range(21)]
    meta["trial_ready"] = {key: samples[-1][key] for key in ("frame", "simulation_time_s", "host_monotonic_ns")}
    first_index = None
    for i in range(402):
        host = t0 + (i + 1) * 50_000_000
        brake = first_done is not None and host - 2_000_000 >= first_done
        if brake and first_index is None:
            first_index = i
        speed = .05 if brake and i > first_index else 5 / 3.6
        samples.append(sample(121 + i, (21 + i) * step, host, "g4", speed, brake, 5 + min(i, first_index or i) * .05))
    return meta, inputs, observed, sut, received, events, samples


def set_speed(row, speed):
    row["speed_mps"] = speed
    row["velocity_mps"] = {"x": speed, "y": 0., "z": 0.}


class MainOracleTests(unittest.TestCase):
    def test_all_scenarios_preserve_message_results_and_add_actual_motion(self):
        for variant in ("A", "B"):
            for scenario in ("T-01", "T-02", "T-03", "T-04"):
                with self.subTest(variant=variant, scenario=scenario):
                    result = evaluate_main_trial(*fixture(variant, scenario))
                    self.assertTrue(result["evidence_valid"], result["evidence_errors"])
                    self.assertEqual(result["operational_failures"], [])
                    self.assertEqual(result["requirements"]["R-09"]["status"], "PASS")
                    self.assertEqual(result["all_checks_passed"], (variant, scenario) != ("A", "T-04"))
                    if (variant, scenario) == ("A", "T-04"):
                        self.assertEqual(result["requirements"]["R-04"]["status"], "FAIL")
                        self.assertEqual(result["requirements"]["R-07"]["status"], "N/A")

    def test_call_deadline_is_inclusive_and_not_converted_to_environment_error(self):
        for duration, expected in ((50_000_000, "PASS"), (50_000_001, "FAIL")):
            data = list(fixture())
            last = data[5][-1]
            last["a_done_ns"] = last["a_rx_ns"] + duration
            self.assertEqual(evaluate_main_trial(*data)["requirements"]["R-06"]["status"], expected)

    def test_first_tick_after_call_must_show_brake_not_a_later_frame(self):
        data = list(fixture())
        first = next(event["a_done_ns"] for event in data[5] if "a_done_ns" in event)
        row = next(row for row in data[6] if row["phase"] == "g4" and row["tick_begin_monotonic_ns"] >= first)
        row["applied_control"]["brake"] = 0
        self.assertEqual(evaluate_main_trial(*data)["requirements"]["R-07"]["status"], "FAIL")

    def test_frame_forty_boundary_uses_float32_step_without_relaxation(self):
        step = struct.unpack("f", struct.pack("f", .05))[0]
        for hold_start, expected in ((30, "PASS"), (31, "FAIL")):
            data = list(fixture(step=step))
            first = next(event["a_done_ns"] for event in data[5] if "a_done_ns" in event)
            after = [row for row in data[6] if row["phase"] == "g4" and row["tick_begin_monotonic_ns"] >= first]
            for offset, row in enumerate(after):
                set_speed(row, .05 if offset >= hold_start else 1.2)
            self.assertEqual(evaluate_main_trial(*data)["requirements"]["R-07"]["status"], expected)

    def test_normal_input_restoration_cannot_release_brake(self):
        data = list(fixture("B", "T-04"))
        data[6][-1]["applied_control"]["brake"] = 0
        self.assertEqual(evaluate_main_trial(*data)["requirements"]["R-08"]["status"], "FAIL")

    def test_missing_adapter_receive_keeps_message_pass_but_blocks_full_evidence(self):
        data = list(fixture())
        data[4].pop()
        result = evaluate_main_trial(*data)
        self.assertFalse(result["evidence_valid"])
        self.assertEqual(result["requirements"]["R-03"]["status"], "PASS")
        self.assertEqual(result["requirements"]["R-09"]["status"], "INCONCLUSIVE")

    def test_invalid_rpc_response_is_not_successful_control(self):
        data = list(fixture())
        next(event for event in data[5] if "response" in event)["response"]["actor_id"] = 999
        self.assertEqual(evaluate_main_trial(*data)["requirements"]["R-06"]["status"], "FAIL")

    def test_missing_frame_or_nonfinite_velocity_cannot_pass(self):
        for change in ("gap", "nan", "speed"):
            data = list(fixture())
            if change == "gap":
                data[6].pop(-4)
            elif change == "nan":
                data[6][-1]["velocity_mps"]["x"] = float("nan")
            else:
                data[6][-1]["speed_mps"] = 999
            self.assertFalse(evaluate_main_trial(*data)["evidence_valid"])

    def test_no_request_but_stationary_vehicle_is_not_successful_negative_control(self):
        data = list(fixture("A", "T-01"))
        set_speed(data[6][80], 0.)
        result = evaluate_main_trial(*data)
        self.assertTrue(result["operational_failures"])
        self.assertFalse(result["all_checks_passed"])

    def test_departing_fixed_road_is_not_ignored(self):
        data = list(fixture("A", "T-01"))
        data[6][-1]["transform"]["x"] += 10
        self.assertTrue(evaluate_main_trial(*data)["operational_failures"])

    def test_missing_run_end_motion_is_not_passed_by_sent_commands(self):
        data = list(fixture())
        data[6] = [row for row in data[6] if row["host_monotonic_ns"] < data[0]["trial_end_ns"]]
        self.assertFalse(evaluate_main_trial(*data)["evidence_valid"])

    def test_changed_physics_blocks_evidence(self):
        data = list(fixture())
        data[0]["vehicle_physics"] = data[0]["vehicle_physics"].replace("mass=1845", "mass=1500")
        self.assertFalse(evaluate_main_trial(*data)["evidence_valid"])

    def test_no_runtime_evidence_is_inconclusive_not_an_observed_motion_failure(self):
        data = list(fixture())
        data[0]["execution_status"] = "ENV_ERROR"
        data[0]["worker_results"] = {}
        data[0]["adapter_prearm_rx"] = []
        for key in ("t0_ns", "trial_end_ns", "trial_global_slot", "armed"):
            data[0].pop(key, None)
        for index in range(1, 7):
            data[index] = []
        result = evaluate_main_trial(*data)
        self.assertFalse(result["evidence_valid"])
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["requirements"]["R-03"]["status"], "INCONCLUSIVE")

    def test_overlapping_synchronous_calls_are_not_valid_evidence(self):
        data = list(fixture())
        calls = [event for event in data[5] if "a_done_ns" in event]
        calls[0]["a_done_ns"] = calls[1]["a_rx_ns"] + 1
        self.assertFalse(evaluate_main_trial(*data)["evidence_valid"])

    def test_request_sent_before_activation_but_received_after_is_not_lost(self):
        data = list(fixture())
        data[0]["adapter_active_ns"] = data[4][0]["host_monotonic_ns"] - 1
        result = evaluate_main_trial(*data)
        self.assertTrue(result["evidence_valid"], result["evidence_errors"])

    def test_missing_prearm_observation_is_not_silently_ignored(self):
        data = list(fixture())
        data[0]["adapter_prearm_rx"] = []
        self.assertFalse(evaluate_main_trial(*data)["evidence_valid"])

    def test_wrong_request_counter_is_a_sut_output_failure(self):
        data = list(fixture())
        target = data[3][-1]
        old = target["raw_frame_hex"]
        raw = bytearray.fromhex(old)
        raw[10] = (raw[10] + 1) % 256
        for rows in (data[2], data[3], data[4], data[5]):
            for row in rows:
                if row["raw_frame_hex"] == old:
                    row["raw_frame_hex"] = raw.hex()
                    if "data_hex" in row:
                        row["data_hex"] = raw[8:].hex()
                    if "request" in row:
                        row["request"]["counter"] = raw[10]
        result = evaluate_main_trial(*data)
        self.assertTrue(result["message_checks"]["sut_output_errors"])
        self.assertTrue(result["operational_failures"])
        self.assertFalse(result["all_checks_passed"])


if __name__ == "__main__":
    unittest.main()
