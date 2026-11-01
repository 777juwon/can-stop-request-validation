"""예비시험 독립 판정의 합성 로그 검사다. 실제 예비시험 결과가 아니다."""

import copy
import struct
import unittest

from tools.message_trial_oracle import evaluate_message_trial


def fixture(variant="A", scenario="T-01"):
    token, origin, arm, t0 = 0x12345678, 1_000_000_000, 1_210_000_000, 13_800_000_000
    end = t0 + 20_000_000_000
    pids = {"sender": 11, "observer": 12, "controller": 13}
    meta = {"variant": variant, "scenario": scenario, "run_token": token, "execution_status": "COMPLETE",
            "coordinator_pid": 10, "worker_pids": pids, "armed": {"host_monotonic_ns": arm},
            "t0_ns": t0, "trial_end_ns": end, "trial_global_slot": 256,
            "preparation_started_monotonic_ns": origin - 100_000_000,
            "preparation_deadline_monotonic_ns": origin + 29_900_000_000,
            "worker_results": {role: {"pid": pid, "role": role, "status": "COMPLETE", "exit_code": 0,
                                       "run_token": token, "done_monotonic_ns": end + 50_000_000}
                               for role, pid in pids.items()}}
    meta.update({role + "_exit_code": 0 for role in pids})
    inputs, observed, sut = [], [], []

    def row(identifier, payload, event, pid, stamp, **extra):
        packet = struct.pack("=IB3x8s", identifier, 8, payload)
        return {"event": event, "pid": pid, "raw_frame_hex": packet.hex(), "arbitration_id": identifier,
                "dlc": 8, "data_hex": payload.hex(), "extended": False, "remote": False, "error_frame": False,
                "host_monotonic_ns": stamp, **extra}

    for global_slot in range(656):
        n = global_slot - 256 if global_slot >= 256 else None
        due = origin + global_slot * 50_000_000
        for identifier in (0x100, 0x101):
            if scenario == "T-03" and n is not None and 100 <= n < 160 and identifier == 0x100:
                continue
            counter = 99 if scenario == "T-04" and n is not None and 100 <= n < 160 and identifier == 0x100 else global_slot % 256
            distance = max(50, 1000 - 5 * (n - 100)) if scenario == "T-02" and n is not None and n >= 100 else 1000
            payload = (struct.pack("<HBBI", distance, counter, 1, token) if identifier == 0x100
                       else bytes((counter, 0, 0, 0)) + token.to_bytes(4, "little"))
            begin = due + (1_000 if identifier == 0x101 else 0)
            inputs.append(row(identifier, payload, "tx", 11, begin, phase="prepare" if n is None else "trial",
                              global_slot=global_slot, slot=n, scheduled_ns=due, s_begin_ns=begin,
                              s_done_ns=begin + 3_000, bytes_sent=16))
            observed.append(row(identifier, payload, "rx", 12, begin + 2_000))
    stop_ns = (t0 + 13_001_000_000 if scenario == "T-02" else t0 + 5_155_003_000
               if scenario == "T-03" or (scenario == "T-04" and variant == "B") else None)
    stamps = [origin - 10_000_000] + list(range(arm + 1_000_000, end + 1, 50_000_000))
    if stop_ns:
        stamps.append(stop_ns)
    for counter, stamp in enumerate(sorted(stamps)):
        stop = stamp < arm or stop_ns is not None and stamp >= stop_ns
        reason = 4 if stamp < arm else (1 if scenario == "T-02" else 3 if scenario == "T-04" else 2) if stop else 0
        payload = bytes((int(stop), reason, counter % 256, 0)) + token.to_bytes(4, "little")
        sut.append(row(0x200, payload, "request_tx", 13, stamp, s_begin_ns=stamp, s_done_ns=stamp + 3_000, bytes_sent=16))
        observed.append(row(0x200, payload, "rx", 12, stamp + 2_000))
    observed.sort(key=lambda item: item["host_monotonic_ns"])
    return meta, inputs, observed, sut


class OracleTests(unittest.TestCase):
    def test_all_eight_design_outcomes_keep_a_t04_requirement_failure(self):
        for variant in ("A", "B"):
            for scenario in ("T-01", "T-02", "T-03", "T-04"):
                with self.subTest(variant=variant, scenario=scenario):
                    result = evaluate_message_trial(*fixture(variant, scenario))
                    self.assertTrue(result["evidence_valid"], result)
                    primary = {"T-01": "R-01", "T-02": "R-02", "T-03": "R-03", "T-04": "R-04"}[scenario]
                    self.assertEqual(result["requirements"][primary]["status"], "FAIL" if (variant, scenario) == ("A", "T-04") else "PASS")
                    self.assertEqual(result["requirements"]["R-07"]["status"], "N/A")

    def test_sender_success_without_observer_cannot_validate_any_requirements(self):
        data = list(fixture())
        data[2] = []
        result = evaluate_message_trial(*data)
        self.assertFalse(result["evidence_valid"])
        self.assertEqual(result["requirements"]["R-01"]["status"], "INCONCLUSIVE")

    def test_raw_input_mutation_and_missing_frame_cannot_pass(self):
        for change in ("mutate", "missing", "duplicate"):
            data = list(fixture())
            if change == "mutate":
                data[1][-1]["raw_frame_hex"] = "00" * 16
            elif change == "missing":
                data[1].pop()
            else:
                data[1].append(copy.deepcopy(data[1][-1]))
            with self.subTest(change=change):
                self.assertFalse(evaluate_message_trial(*data)["evidence_valid"])

    def test_request_too_early_is_not_hidden_by_successful_motion_or_internal_verdict(self):
        data = list(fixture("B", "T-04"))
        # 원시 요청과 독립 관측을 함께 앞당겨 판정기의 시각 경계를 검사한다.
        stop = next(row for row in data[3] if bytes.fromhex(row["data_hex"])[1] == 3)
        matching = next(row for row in data[2] if row["raw_frame_hex"] == stop["raw_frame_hex"] and row["host_monotonic_ns"] >= data[0]["t0_ns"])
        for key in ("host_monotonic_ns", "s_begin_ns", "s_done_ns"):
            stop[key] -= 100_000_000
        matching["host_monotonic_ns"] -= 100_000_000
        data[2].sort(key=lambda row: row["host_monotonic_ns"])
        result = evaluate_message_trial(*data)
        self.assertEqual(result["requirements"]["R-04"]["status"], "FAIL")

    def test_clock_pid_arm_and_worker_evidence_are_required(self):
        for change in ("pid", "arm", "worker", "end", "prepare"):
            data = list(fixture())
            if change == "pid":
                data[0]["worker_pids"]["observer"] = 11
            elif change == "arm":
                data[0]["armed"]["host_monotonic_ns"] = 1_000_000_000
            elif change == "worker":
                data[0]["worker_results"]["controller"]["status"] = "SUT_ERROR"
            elif change == "end":
                data[0]["trial_end_ns"] += 1
            else:
                data[0]["preparation_deadline_monotonic_ns"] += 1
            with self.subTest(change=change):
                self.assertFalse(evaluate_message_trial(*data)["evidence_valid"])

    def test_partial_execution_keeps_missing_evidence_inconclusive(self):
        data = list(fixture())
        data[0]["execution_status"] = "INTERRUPTED"
        data[2] = []
        result = evaluate_message_trial(*data)
        self.assertFalse(result["evidence_valid"])
        self.assertTrue(result["missing_evidence"])

    def test_silent_controller_cannot_satisfy_negative_control_on_counts_alone(self):
        data = list(fixture())
        data[2] = [row for row in data[2] if row["arbitration_id"] != 0x200]
        data[3] = []
        self.assertFalse(evaluate_message_trial(*data)["evidence_valid"])


if __name__ == "__main__":
    unittest.main()
