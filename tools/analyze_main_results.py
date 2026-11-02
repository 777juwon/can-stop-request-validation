#!/usr/bin/env python3
"""완료된 원래80개 시도를 오프라인 검증하고 실패/결측을 보존해 집계한다.

실험 파일과 동결 코드는 읽기만 한다. 출력은 새 폴더에만 작성한다.
서버, CAN 소켓과 차량을 실행하지 않는다.
"""

import argparse
from collections import Counter, defaultdict, deque
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.main_plan import canonical, digest, project_output, verify_frozen
from tools.main_trial_oracle import evaluate_main_trial

CHECKPOINT = ROOT / "evidence/implementation/main-preparation-20261101-01/checkpoint-080.json"
LOGS = ("input_events", "can_observer", "sut_events", "adapter_rx", "adapter_events", "vehicle_states")
METRICS = {
    "request_latency_ms": ("ms", "요청 관측: 기준 입력 s_done부터 q_obs까지"),
    "first_adapter_ms": ("ms", "최초 제동 요청의 a_rx부터 a_done까지"),
    "median_adapter_ms": ("ms", "각 실행 내부의 유효 제동 호출 처리시간 중앙값"),
    "max_adapter_ms": ("ms", "각 실행 내부의 유효 제동 호출 처리시간 최댓값"),
    "stop_completion_sim_s": ("simulation_s", "최초 제동 적용부터 0.5초 정지 유지 완료까지"),
    "preparation_host_s": ("host_s", "준비 시작부터 T0까지"),
    "max_sender_lateness_ms": ("ms", "본 입력의 실제 송신 시작과 명목 슬롯 시각 차이의 최댓값"),
    "max_tick_lateness_ms": ("ms", "본 구간 차량 tick의 기록된 일정 지연 최댓값"),
}
EVIDENCE = {
    "R-01": "input_events.jsonl;can_observer.jsonl", "R-02": "input_events.jsonl;can_observer.jsonl",
    "R-03": "input_events.jsonl;can_observer.jsonl", "R-04": "input_events.jsonl;can_observer.jsonl",
    "R-05": "input_events.jsonl;can_observer.jsonl", "R-06": "adapter_rx.jsonl;adapter_events.jsonl",
    "R-07": "vehicle_states.jsonl", "R-08": "can_observer.jsonl;adapter_events.jsonl;vehicle_states.jsonl",
    "R-09": ";".join(name + ".jsonl" for name in LOGS),
}


def file_bytes(path, expected=None):
    """검토된 결과를 나중에 바꾼 경우 집계를 중단한다."""
    data = path.read_bytes()
    if expected is not None and digest(data) != expected:
        raise ValueError("기록된 SHA와 다른 파일: " + str(path))
    return data


def matched_calls(meta, sut, events):
    """초기 큐와 순번 회전을 FIFO로 대응하고 입력 종료 후 신규 사건을 제외한다."""
    queues = defaultdict(deque)
    for row in sut:
        if row.get("event") == "request_tx":
            queues[row["raw_frame_hex"]].append(row)
    for row in meta["adapter_prearm_rx"]:
        if not queues[row["raw_frame_hex"]]:
            raise ValueError("초기 큐 송신 대응 누락")
        queues[row["raw_frame_hex"]].popleft()
    calls = []
    for event in events:
        if event.get("event") != "request":
            continue
        queue = queues[event["raw_frame_hex"]]
        if not queue:
            raise ValueError("adapter 이벤트의 송신 대응 누락")
        source = queue.popleft()
        if source["s_begin_ns"] <= meta["trial_end_ns"] and event.get("call_completed") is True:
            duration = (event["a_done_ns"] - event["a_rx_ns"]) / 1e6
            if duration < 0 or not math.isfinite(duration):
                raise ValueError("비정상 adapter 처리시간")
            calls.append({"source": source, "event": event, "duration_ms": duration})
    if any(queues.values()):
        raise ValueError("adapter 이벤트 전체 대응 누락")
    return calls


def run_metrics(meta, logs, checks):
    """반복 하나를 통계 단위로 사용한다. 미관측/미적용 수치는 None이다."""
    calls = matched_calls(meta, logs["sut_events"], logs["adapter_events"])
    if len(calls) != checks["metrics"]["adapter_calls"]:
        raise ValueError("제어 호출 분모 불일치")
    durations = [r["duration_ms"] for r in calls]
    observed = checks["metrics"]["first_stop_observed_ns"]
    ref_slot = 260 if meta["scenario"] == "T-02" else 99
    reference = next((r for r in logs["input_events"] if r.get("event") == "tx"
                      and r.get("phase") == "trial" and r.get("slot") == ref_slot
                      and int.from_bytes(bytes.fromhex(r["raw_frame_hex"])[:4], sys.byteorder) == 0x100), None)
    request = None if observed is None else (observed - reference["s_done_ns"]) / 1e6
    if request is not None and not math.isclose(request, checks["metrics"]["request_after_reference_send_done_ms"], abs_tol=1e-9):
        raise ValueError("요청 관측 경계 계산 불일치")
    applied, hold = checks["metrics"]["first_brake_applied"], checks["metrics"]["stop_hold"]
    stop = None if not applied or not hold else hold["last_simulation_time_s"] - applied["simulation_time_s"]
    sender = [r for r in logs["input_events"] if r.get("event") == "tx" and r.get("phase") == "trial"]
    vehicle = [r for r in logs["vehicle_states"] if r.get("phase") == "g4"]
    return {
        "request_state": "OBSERVED" if observed is not None else "NOT_REQUIRED" if meta["scenario"] == "T-01" else "NOT_OBSERVED",
        "request_latency_ms": request, "adapter_calls": len(calls),
        "first_adapter_ms": durations[0] if durations else None,
        "median_adapter_ms": statistics.median(durations) if durations else None,
        "max_adapter_ms": max(durations) if durations else None,
        "stop_completion_sim_s": stop,
        "stop_completion_frame_intervals": None if not hold or not applied else hold["last_frame"] - applied["frame"],
        "preparation_host_s": (meta["t0_ns"] - meta["preparation_started_monotonic_ns"]) / 1e9,
        "max_sender_lateness_ms": max(r["s_begin_ns"] - r["scheduled_ns"] for r in sender) / 1e6,
        "max_tick_lateness_ms": max(r["schedule_lateness_ns"] for r in vehicle) / 1e6,
    }


def distribution(values):
    """None은 결측으로 별도 집계하고 부울/비유한 수치를 거부한다."""
    valid = [v for v in values if v is not None]
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in valid):
        raise ValueError("통계에 비정상 수치가 포함됐습니다")
    return {"observed_n": len(valid), "missing_n": len(values) - len(valid),
            "min": min(valid) if valid else None, "median": statistics.median(valid) if valid else None,
            "max": max(valid) if valid else None}


def summarize(records):
    cells, stats, trace = [], [], []
    for scenario in ("T-01", "T-02", "T-03", "T-04"):
        for variant in ("A", "B"):
            group = [r for r in records if r["scenario"] == scenario and r["variant"] == variant]
            cells.append({"scenario": scenario, "variant": variant, "original_attempts": len(group),
                          **{key: sum(r["status"] == key for r in group) for key in ("PASS", "FAIL")},
                          "COMPLETE": sum(r["execution_status"] == "COMPLETE" for r in group),
                          "cleanup_PASS": sum(r["cleanup_status"] == "PASS" for r in group),
                          "not_observed": sum(r["request_state"] == "NOT_OBSERVED" for r in group)})
            for name, (unit, meaning) in METRICS.items():
                # 정상 비정지 조건의 요청/제동/정지 지표에는 관측 의무가 없다.
                applicable = group if name in ("preparation_host_s", "max_sender_lateness_ms", "max_tick_lateness_ms") or scenario != "T-01" else []
                stats.append({"scenario": scenario, "variant": variant, "metric": name, "unit": unit,
                              "definition": meaning, "eligible_n": len(applicable),
                              "not_applicable_n": len(group) - len(applicable),
                              **distribution([r[name] for r in applicable])})
            for n in range(1, 10):
                requirement = f"R-{n:02}"
                counts = Counter(r[requirement] for r in group)
                trace.append({"scenario": scenario, "variant": variant, "requirement": requirement,
                              **{key: counts[key] for key in ("PASS", "FAIL", "N/A", "INCONCLUSIVE", "NOT_APPLICABLE_TO_SCENARIO")},
                              "evidence_files": EVIDENCE[requirement]})
    return cells, stats, trace


def load_campaign(root):
    manifest_bytes = (root / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    verify_frozen(manifest)
    checkpoint = json.loads(CHECKPOINT.read_text())
    expected = {r["run_id"]: r for r in checkpoint["runs"]}
    if set(expected) != {r["run_id"] for r in manifest["runs"]} or len(expected) != 80:
        raise ValueError("80개 원래 ID와 최종 검토 목록 불일치")
    if {p.name for p in (root / "runs").iterdir()} != set(expected):
        raise ValueError("실행 폴더에 누락되거나 추가된 원래 ID가 있습니다")
    records, representatives = [], {}
    hashes = {str(root.relative_to(ROOT) / "manifest.json"): digest(manifest_bytes)}
    for name, expected_hash in manifest["source_sha256"].items():
        archived = root / "source" / name
        hashes[str(archived.relative_to(ROOT))] = digest(file_bytes(archived, expected_hash))
    for row in manifest["runs"]:
        folder = root / "runs" / row["run_id"]
        meta_raw = file_bytes(folder / "metadata.json", expected[row["run_id"]]["metadata_sha256"])
        result_raw = file_bytes(folder / "result.json", expected[row["run_id"]]["result_sha256"])
        meta, result = json.loads(meta_raw), json.loads(result_raw)
        if any(manifest["source_sha256"].get("tools/" + name) != sha for name, sha in meta["source_sha256"].items()):
            raise ValueError("실행 당시 소스와 동결 소스 불일치")
        claim_raw = file_bytes(root / "attempts" / (row["run_id"] + ".json"))
        claim = json.loads(claim_raw)
        if (meta["planned_run"] != row or meta["run_token"] != row["run_token"]
                or claim["run_id"] != row["run_id"] or claim["run_token"] != row["run_token"]
                or claim["config_sha256"] != manifest["config_sha256"]
                or meta["config_sha256"] != manifest["config_sha256"]
                or meta["fixture_sha256"] != manifest["fixture_sha256"][row["scenario"]]
                or result["scope"] != "MAIN_CARLA_ORIGINAL_ATTEMPT" or result["main_trials_executed"] != 1):
            raise ValueError("원래 시도 식별/동결 불일치: " + row["run_id"])
        logs = {}
        for name in LOGS:
            data = file_bytes(folder / (name + ".jsonl"))
            hashes[str((folder / (name + ".jsonl")).relative_to(ROOT))] = digest(data)
            logs[name] = [json.loads(line) for line in data.splitlines() if line.strip()]
        for name, data in (("metadata.json", meta_raw), ("result.json", result_raw)):
            hashes[str((folder / name).relative_to(ROOT))] = digest(data)
        hashes[str((root / "attempts" / (row["run_id"] + ".json")).relative_to(ROOT))] = digest(claim_raw)
        checks = evaluate_main_trial(meta, *(logs[name] for name in LOGS))
        if canonical(checks) != canonical(result["checks"]):
            raise ValueError("동결 oracle 재계산과 과거 판정 불일치: " + row["run_id"])
        if meta["execution_status"] != "COMPLETE" or result["execution_status"] != "COMPLETE" or not checks["evidence_valid"]:
            raise ValueError("완료/근거 전제를 충족하지 못한 시도: " + row["run_id"])
        status = "FAIL" if checks["failures"] else "PASS"
        if result["status"] != status:
            raise ValueError("저장한 전체 판정 불일치")
        record = {key: row[key] for key in ("run_id", "scenario", "variant", "repeat", "order")}
        record.update(execution_status=result["execution_status"], status=status,
                      cleanup_status=result["cleanup_status"], evidence_valid=checks["evidence_valid"],
                      **run_metrics(meta, logs, checks))
        for n in range(1, 10):
            req = f"R-{n:02}"
            record[req] = checks["requirements"].get(req, {}).get("status", "NOT_APPLICABLE_TO_SCENARIO")
        records.append(record)
        # 결과의 모양으로 고르지 않고 각 셀의 첫 반복을 대표로 고정한다.
        if row["repeat"] == 1:
            representatives[meta["scenario"], meta["variant"]] = {"meta": meta, "logs": logs, "checks": checks}
    return records, representatives, hashes, manifest


def write_csv(path, rows):
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def analyze(root, output, figures=True):
    if output.resolve().is_relative_to(root.resolve()):
        raise ValueError("분석 출력은 실험 원본 폴더 밖에 작성해야 합니다")
    if output.exists():
        raise FileExistsError("기존 분석 폴더는 재사용하지 않습니다: " + str(output))
    records, examples, hashes, manifest = load_campaign(root)
    cells, stats, trace = summarize(records)
    output.mkdir(parents=True, exist_ok=False)
    write_csv(output / "per_run_metrics.csv", records)
    write_csv(output / "cell_outcomes.csv", cells)
    write_csv(output / "metric_statistics.csv", stats)
    write_csv(output / "requirement_traceability.csv", trace)
    pairs = []
    for scenario in ("T-01", "T-02", "T-03", "T-04"):
        for repeat in range(1, 11):
            a, b = [next(r for r in records if r["scenario"] == scenario and r["repeat"] == repeat and r["variant"] == v) for v in ("A", "B")]
            pairs.append({"scenario": scenario, "repeat": repeat, "A_run_id": a["run_id"], "B_run_id": b["run_id"],
                          "A_request_ms": a["request_latency_ms"], "B_request_ms": b["request_latency_ms"],
                          "B_minus_A_request_ms": None if a["request_latency_ms"] is None or b["request_latency_ms"] is None else b["request_latency_ms"] - a["request_latency_ms"]})
    write_csv(output / "paired_observations.csv", pairs)
    source_names = ("tools/analyze_main_results.py", "tools/plot_main_results.py", "requirements-analysis.txt", "requirements-analysis.lock.txt")
    provenance = {"recorded_utc": datetime.now(timezone.utc).isoformat(), "campaign": str(root.relative_to(ROOT)),
                  "original_attempts": len(records), "execution_status_counts": dict(Counter(r["execution_status"] for r in records)),
                  "run_status_counts": dict(Counter(r["status"] for r in records)),
                  "cleanup_status_counts": dict(Counter(r["cleanup_status"] for r in records)),
                  "frozen_oracle_recomputed_and_matches": 80, "source_sha256": manifest["source_sha256"],
                  "analysis_source_sha256": {n: digest((ROOT / n).read_bytes()) for n in source_names if (ROOT / n).exists()},
                  "checkpoint_sha256": digest(CHECKPOINT.read_bytes()), "input_file_sha256": hashes,
                  "statistics_unit": "original_run; adapter최대값은 각run 내부최댓값의 분포",
                  "representative_rule": "각 scenario/variant의 repeat=1, 총8개. 결과 기반 선별 없음",
                  "representative_run_ids": [v["meta"]["run_id"] for v in examples.values()],
                  "missing_policy": "미요청은 None/CSV빈셀. NOT_REQUIRED/NOT_OBSERVED/요구사항N/A/시나리오비해당 구분",
                  "server_shutdown_status": "NOT_CONFIRMED", "new_experiments_executed": 0,
                  "python_version": sys.version}
    if figures:
        from tools.plot_main_results import render
        provenance["plot_environment"] = render(output, records, cells, examples)
    write_json(output / "analysis_manifest.json", provenance)
    print(json.dumps({"status": "COMPLETE", "original_attempts": len(records),
                      "outcomes": provenance["run_status_counts"], "output_dir": str(output), "new_experiments_executed": 0}))
    return records, stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, default=Path("runs/main-v1-20261101"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--no-figures", action="store_true", help="표/통계 검증만 수행")
    args = parser.parse_args()
    try:
        analyze(project_output(args.campaign), project_output(args.output_dir), not args.no_figures)
    except (OSError, ValueError, KeyError, ImportError) as exc:
        print("분석 중단: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
