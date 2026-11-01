#!/usr/bin/env python3
"""사용자가 CARLA 없이 A/B 네 시나리오 예비시험을 순서대로 실행한다.

명령 종료코드 0은 기록 가능한 예비시험 완료를 뜻한다. 요구사항 FAIL은
결과에 그대로 남긴다. 본시험 80회나 차량 운동을 실행한 것으로 집계하지 않는다.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
import traceback


REPOSITORY = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY))
from tools.g3_carla_smoke import RunError, read_optional_jsonl
from tools.g3_request_smoke import inspect_link, write_json
from tools.g4_can_workers import atomic_write_json
from tools.g4_carla_smoke import check_worker_record, worker_failure
from tools.message_trial_oracle import evaluate_message_trial


SCOPE = "MESSAGE_LEVEL_PRELIMINARY_ONLY"
SCENARIOS = ("T-01", "T-02", "T-03", "T-04")


def run_case(output, interface, variant, scenario):
    """독립 관측기를 먼저 준비하고 초기화가 분리된 한 조합을 실행한다."""
    output.mkdir(parents=True, exist_ok=False)
    meta = {"scope": SCOPE, "variant": variant, "scenario": scenario, "run_id": output.name,
            "run_token": secrets.randbits(32), "coordinator_pid": os.getpid(),
            "baseline": "v1.0", "carla_executed": False, "main_trials_executed": 0,
            "execution_status": "ENV_ERROR", "started_utc": datetime.now(timezone.utc).isoformat(),
            "worker_pids": {}, "worker_results": {}}
    children, handles, commands, cleanup = {}, [], [], []

    def check_workers():
        for role, child in children.items():
            code = child.poll()
            if code is not None and (role != "sender" or code != 0):
                raise worker_failure(output, role, child)

    def wait_record(name, deadline):
        while not (output / name).exists():
            check_workers()
            if time.monotonic_ns() >= deadline:
                raise RunError("ENV_ERROR", name + " 대기 기한 초과")
            time.sleep(.01)
        record = json.loads((output / name).read_text())
        if record.get("run_token") != meta["run_token"]:
            raise RunError("INPUT_ERROR", name + " token 불일치")
        return record

    def command(name):
        atomic_write_json(output / name, {"run_token": meta["run_token"], "host_monotonic_ns": time.monotonic_ns()})

    try:
        meta["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=REPOSITORY).strip()
        names = ("run_message_preliminary.py", "message_trial_oracle.py", "sequence_controller_core.py",
                 "g4_controller_core.py", "g4_can_workers.py", "g4_carla_smoke.py",
                 "g3_request_smoke.py", "g3_integration_can.py", "g3_carla_smoke.py")
        meta["source_sha256"] = {name: hashlib.sha256((REPOSITORY / "tools" / name).read_bytes()).hexdigest() for name in names}
        meta["dbc_sha256"] = hashlib.sha256((REPOSITORY / "config/stop_request_v1.dbc").read_bytes()).hexdigest()
        meta["interface"] = inspect_link(interface, output)
        start = time.monotonic_ns()
        deadline = start + 30_000_000_000
        meta.update(preparation_started_monotonic_ns=start, preparation_deadline_monotonic_ns=deadline)
        for role in ("observer", "controller", "sender"):
            argv = [sys.executable, "-I", str(REPOSITORY / "tools/g4_can_workers.py"), "--worker", role,
                    "--interface", interface, "--output-dir", str(output), "--run-token", str(meta["run_token"]),
                    "--variant", variant, "--scenario", scenario]
            stream = (output / (role + "_stderr.txt")).open("x", encoding="utf-8")
            handles.append(stream)
            children[role] = subprocess.Popen(argv, stderr=stream, stdout=subprocess.DEVNULL)
            meta["worker_pids"][role] = children[role].pid
            commands.append({"role": role, "argv": argv, "pid": children[role].pid})
            wait_record(role + "_ready.json", min(deadline, time.monotonic_ns() + 3_000_000_000))
        meta["controller_input_ready"] = wait_record("controller_input_ready.json", deadline)
        command("controller_arm.json")
        meta["armed"] = wait_record("controller_armed.json", deadline)
        command("trial_requested.json")
        record = wait_record("trial_started.json", deadline)
        meta.update({key: record[key] for key in ("t0_ns", "t0_done_ns", "trial_global_slot", "trial_first_scheduled_ns", "trial_end_ns")})
        if meta["t0_ns"] > deadline:
            raise RunError("ENV_ERROR", "기동과 T0의 30초 기한 초과")
        while children["sender"].poll() is None:
            check_workers()
            if time.monotonic_ns() > meta["trial_end_ns"] + 3_000_000_000:
                raise RunError("INPUT_ERROR", "송신기 종료 기한 초과")
            time.sleep(.01)
        check_worker_record("sender", children["sender"].pid, children["sender"].poll(),
                            json.loads((output / "sender_result.json").read_text()))
        meta["execution_status"] = "COMPLETE"
    except (Exception, KeyboardInterrupt) as exc:
        meta.update(execution_status=exc.status if isinstance(exc, RunError) else
                    "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else
                    "ENV_ERROR" if isinstance(exc, (OSError, subprocess.TimeoutExpired)) else "TOOL_ERROR",
                    error=str(exc))
        (output / "error.txt").write_text(traceback.format_exc())
    finally:
        for role in ("controller", "sender", "observer"):
            child = children.get(role)
            if child is None:
                continue
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    child.kill()
                    try:
                        child.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        cleanup.append(role + ": 강제 종료 대기 초과")
                    cleanup.append(role + ": 종료 유예 초과")
            meta[role + "_exit_code"] = child.poll()
            try:
                result = json.loads((output / (role + "_result.json")).read_text())
                meta["worker_results"][role] = result
                check_worker_record(role, child.pid, child.poll(), result)
            except (OSError, ValueError, RunError) as exc:
                if meta["execution_status"] == "COMPLETE":
                    meta["execution_status"] = exc.status if isinstance(exc, RunError) else "EVIDENCE_ERROR"
                meta.setdefault("worker_errors", []).append(str(exc))
        for stream in handles:
            stream.close()
        meta.update(finished_utc=datetime.now(timezone.utc).isoformat(), cleanup_errors=cleanup)
        try:
            checks = evaluate_message_trial(meta, read_optional_jsonl(output / "input_events.jsonl"),
                                             read_optional_jsonl(output / "can_observer.jsonl"),
                                             read_optional_jsonl(output / "sut_events.jsonl"))
        except Exception as exc:
            checks = {"evidence_valid": False, "requirements": {}, "oracle_error": str(exc)}
            (output / "oracle_error.txt").write_text(traceback.format_exc())
        if meta["execution_status"] == "COMPLETE":
            if cleanup or not checks["evidence_valid"]:
                meta["execution_status"] = "EVIDENCE_ERROR"
            elif checks.get("sut_output_errors"):
                meta["execution_status"] = "SUT_ERROR"
        result = {"scope": SCOPE, "execution_status": meta["execution_status"], "variant": variant,
                  "scenario": scenario, "checks": checks, "main_trials_executed": 0, "carla_executed": False}
        write_json(output / "metadata.json", meta)
        write_json(output / "commands.json", commands)
        write_json(output / "verdict.json", result)
    return result


def campaign_summary(cases, planned_count):
    """시도한 조합, 정상 완료와 미시작 수를 섞지 않고 요구사항 FAIL을 유지한다."""
    completed = sum(case["execution_status"] == "COMPLETE" for case in cases)
    done = len(cases) == planned_count and completed == planned_count
    failed = sum(row["status"] == "FAIL" for case in cases for row in case["requirements"].values())
    status = "COMPLETE_WITH_REQUIREMENT_FAILURES" if done and failed else "COMPLETE" if done else "INCOMPLETE"
    return {"scope": SCOPE, "status": status, "cases_attempted": len(cases), "cases_completed": completed,
            "cases_not_started": max(0, planned_count - len(cases)), "planned_cases": planned_count,
            "requirement_fail_count": failed, "cases": cases, "carla_executed": False, "main_trials_executed": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--interface", default="vcan0")
    parser.add_argument("--variant", choices=("A", "B"))
    parser.add_argument("--scenario", choices=SCENARIOS)
    args = parser.parse_args()
    try:
        args.output_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        parser.error("기존 출력 폴더는 재사용하지 않습니다")

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt("종료 신호")

    signal.signal(signal.SIGTERM, interrupted)
    planned = [(scenario, variant) for scenario in ([args.scenario] if args.scenario else SCENARIOS)
               for variant in ([args.variant] if args.variant else ("A", "B"))]
    write_json(args.output_dir / "planned_cases.json", [{"case_id": f"P-{scenario}-{variant}", "scenario": scenario, "variant": variant}
                                                       for scenario, variant in planned])
    cases = []
    for scenario, variant in planned:
        directory = args.output_dir / f"P-{scenario}-{variant}"
        result = run_case(directory, args.interface, variant, scenario)
        cases.append({"path": str(directory), "variant": variant, "scenario": scenario,
                      "execution_status": result["execution_status"],
                      "requirements": result["checks"]["requirements"]})
        print(json.dumps(cases[-1], ensure_ascii=False), flush=True)
        if result["execution_status"] != "COMPLETE":
            break
    summary = campaign_summary(cases, len(planned))
    write_json(args.output_dir / "summary.json", summary)
    print(json.dumps({"status": summary["status"], "output_dir": str(args.output_dir), "main_trials_executed": 0}))
    return 0 if summary["cases_completed"] == len(planned) else 1


if __name__ == "__main__":
    raise SystemExit(main())
