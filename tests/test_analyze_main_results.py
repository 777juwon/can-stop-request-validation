"""오프라인 분석의 결측, 호출 대응과 통계 분모를 검증한다."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_main_trial_oracle import fixture
from tools import analyze_main_results as analysis
from tools.main_trial_oracle import evaluate_main_trial


def metrics_fixture(variant="A", scenario="T-01"):
    meta, inputs, observed, sut, received, events, samples = fixture(variant, scenario)
    for sample in samples:
        sample["schedule_lateness_ns"] = 1000
    logs = dict(zip(analysis.LOGS, (inputs, observed, sut, received, events, samples)))
    checks = evaluate_main_trial(meta, inputs, observed, sut, received, events, samples)
    return meta, logs, checks


class StatisticsTests(unittest.TestCase):
    def test_missing_values_are_not_zero_latency(self):
        self.assertEqual(analysis.distribution([None, None]),
                         {"observed_n": 0, "missing_n": 2, "min": None, "median": None, "max": None})
        self.assertEqual(analysis.distribution([1., None, 3.])["median"], 2.)

    def test_invalid_numbers_do_not_silently_enter_statistics(self):
        for value in (True, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                analysis.distribution([value])

    def test_requirement_failure_is_kept_in_cell_counts(self):
        rows = []
        for variant in ("A", "B"):
            row = {"scenario": "T-04", "variant": variant, "status": "FAIL" if variant == "A" else "PASS",
                   "execution_status": "COMPLETE", "cleanup_status": "PASS", "request_state": "NOT_OBSERVED" if variant == "A" else "OBSERVED"}
            row.update({key: None if variant == "A" else 2. for key in analysis.METRICS})
            row.update({f"R-{n:02}": "NOT_APPLICABLE_TO_SCENARIO" for n in range(1, 10)})
            row["R-04"] = row["status"]
            rows.append(row)
        cells, stats, trace = analysis.summarize(rows)
        a = next(c for c in cells if c["scenario"] == "T-04" and c["variant"] == "A")
        self.assertEqual((a["FAIL"], a["COMPLETE"], a["not_observed"]), (1, 1, 1))
        stat = next(s for s in stats if s["scenario"] == "T-04" and s["variant"] == "A" and s["metric"] == "request_latency_ms")
        self.assertEqual((stat["observed_n"], stat["missing_n"], stat["median"]), (0, 1, None))
        self.assertEqual(next(t for t in trace if t["scenario"] == "T-04" and t["variant"] == "A" and t["requirement"] == "R-04")["FAIL"], 1)

    def test_per_run_maximum_statistics_do_not_pool_different_call_counts(self):
        rows = []
        for maximum, calls in ((1., 1000), (40., 1)):
            row = {"scenario": "T-02", "variant": "A", "status": "PASS", "execution_status": "COMPLETE",
                   "cleanup_status": "PASS", "request_state": "OBSERVED", "adapter_calls": calls}
            row.update({key: maximum for key in analysis.METRICS})
            row.update({f"R-{n:02}": "PASS" for n in range(1, 10)})
            rows.append(row)
        _, stats, _ = analysis.summarize(rows)
        stat = next(r for r in stats if r["scenario"] == "T-02" and r["variant"] == "A" and r["metric"] == "max_adapter_ms")
        self.assertEqual((stat["observed_n"], stat["median"]), (2, 20.5))


class ExtractionTests(unittest.TestCase):
    def test_no_stop_required_and_missing_stop_remain_distinct(self):
        for variant, scenario, expected in (("A", "T-01", "NOT_REQUIRED"), ("A", "T-04", "NOT_OBSERVED")):
            meta, logs, checks = metrics_fixture(variant, scenario)
            row = analysis.run_metrics(meta, logs, checks)
            self.assertEqual(row["request_state"], expected)
            for metric in ("request_latency_ms", "first_adapter_ms", "max_adapter_ms", "stop_completion_sim_s"):
                self.assertIsNone(row[metric])

    def test_real_velocity_stop_window_and_host_request_are_separate(self):
        meta, logs, checks = metrics_fixture("B", "T-03")
        row = analysis.run_metrics(meta, logs, checks)
        self.assertEqual(row["request_state"], "OBSERVED")
        self.assertAlmostEqual(row["request_latency_ms"], checks["metrics"]["request_after_reference_send_done_ms"])
        self.assertAlmostEqual(row["stop_completion_sim_s"], .55)
        self.assertGreater(row["adapter_calls"], 0)

    def test_counter_wrap_uses_fifo_and_excludes_post_window_new_request(self):
        meta = {"adapter_prearm_rx": [{"raw_frame_hex": "initial"}], "trial_end_ns": 100}
        sut = [{"event": "request_tx", "raw_frame_hex": "initial", "s_begin_ns": 0}]
        sut += [{"event": "request_tx", "raw_frame_hex": "same", "s_begin_ns": n} for n in (10, 80, 101)]
        events = [{"event": "request", "raw_frame_hex": "same", "call_completed": True,
                   "a_rx_ns": n, "a_done_ns": n + 1} for n in (12, 82, 103)]
        calls = analysis.matched_calls(meta, sut, events)
        self.assertEqual([c["source"]["s_begin_ns"] for c in calls], [10, 80])

    def test_missing_adapter_event_cannot_be_ignored(self):
        meta, logs, _ = metrics_fixture("B", "T-03")
        with self.assertRaises(ValueError):
            analysis.matched_calls(meta, logs["sut_events"], logs["adapter_events"][:-1])


class GuardTests(unittest.TestCase):
    def test_output_cannot_modify_experiment_archive(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(analysis, "load_campaign") as load:
            root = Path(directory) / "campaign"
            with self.assertRaises(ValueError):
                analysis.analyze(root, root / "analysis")
            load.assert_not_called()

    def test_changed_evidence_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "result.json"
            p.write_text("{}")
            with self.assertRaises(ValueError):
                analysis.file_bytes(p, "0" * 64)

    def test_existing_output_is_not_overwritten_or_even_audited(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(analysis, "load_campaign") as load:
            with self.assertRaises(FileExistsError):
                analysis.analyze(Path("unused"), Path(directory))
            load.assert_not_called()

    def test_csv_none_is_empty_and_line_endings_are_portable(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "metrics.csv"
            analysis.write_csv(p, [{"id": "A", "latency_ms": None}])
            self.assertEqual(p.read_bytes(), b"id,latency_ms\nA,\n")


if __name__ == "__main__":
    unittest.main()
