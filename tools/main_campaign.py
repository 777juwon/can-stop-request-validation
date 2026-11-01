#!/usr/bin/env python3
"""고정 설정과 80개 원래 시도를 준비하고 사용자가 단계별로 실행한다.

prepare/status는 CARLA/CAN을 실행하지 않는다. check/run은 사용자가 전용
서버를 준비한 후 실행한다. 원래 ID는 실패해도 재사용하지 않는다.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.g4_can_workers import atomic_write_json
from tools.g4_carla_smoke import run as run_vehicle
from tools.main_plan import (SOURCE_FILES, canonical, digest, fixture_digest, load_config, load_rows,
                             project_output, source_hashes, verify_frozen, verify_run_rows)


@contextmanager
def campaign_lock(directory):
    """프로세스가 사라지면 해제되는 잠금으로 같은 계획의 동시 실행을 막는다."""
    with (directory / "campaign.lock").open("a+") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("다른 프로세스가 같은 계획을 사용 중입니다") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def prepare(directory):
    config, rows, hashes = load_config(), load_rows(), source_hashes()
    directory.mkdir(parents=True, exist_ok=False)
    token_base = secrets.randbits(32)
    rows = [{**row, "run_token": (token_base + i) % (2 ** 32)} for i, row in enumerate(rows)]
    manifest = {"schema_version": 1, "baseline": "v1.0", "prepared_utc": datetime.now(timezone.utc).isoformat(),
                "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "config": config, "config_sha256": digest(canonical(config)), "source_sha256": hashes,
                "fixture_sha256": {scenario: fixture_digest(scenario) for scenario in ("T-01", "T-02", "T-03", "T-04")},
                "runs": rows, "main_trials_executed_at_preparation": 0}
    (directory / "runs").mkdir()
    (directory / "attempts").mkdir()
    (directory / "source").mkdir()
    for name in SOURCE_FILES:
        destination = directory / "source" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write((ROOT / name).read_bytes())
    atomic_write_json(directory / "manifest.json", manifest)
    return manifest


def status(directory, manifest):
    """원래 시도 여부와 요구사항 판정을 분리하며 미결과 claim도 보존한다."""
    verify_run_rows(manifest["runs"])
    records = []
    for row in manifest["runs"]:
        claim = directory / "attempts" / (row["run_id"] + ".json")
        result_path = directory / "runs" / row["run_id"] / "result.json"
        if not claim.exists():
            state, requirements = "NOT_STARTED", {}
            if result_path.exists() or (directory / "runs" / row["run_id"]).exists():
                raise ValueError("claim 없는 기존 실행 폴더: " + row["run_id"])
        elif not result_path.exists():
            # 실행 중 조회와 비정상 중단을 파일 부재만으로 구별하지 않는다.
            state, requirements = "RESULT_NOT_RECORDED", {}
        else:
            result = json.loads(result_path.read_text())
            meta = json.loads((result_path.parent / "metadata.json").read_text())
            if (meta.get("run_id") != row["run_id"] or meta.get("run_token") != row["run_token"]
                    or meta.get("config_sha256") != manifest["config_sha256"]
                    or result.get("scope") != "MAIN_CARLA_ORIGINAL_ATTEMPT"
                    or result.get("main_trials_executed") != 1):
                raise ValueError("원래 ID에 대응하지 않는 실행 근거: " + row["run_id"])
            state, requirements = result["execution_status"], result["checks"].get("requirements", {})
            if result.get("cleanup_status") != "PASS" and state == "COMPLETE":
                state = "CLEANUP_ERROR"
        if claim.exists():
            reserved = json.loads(claim.read_text())
            if (reserved.get("run_id") != row["run_id"] or reserved.get("run_token") != row["run_token"]
                    or reserved.get("config_sha256") != manifest["config_sha256"]):
                raise ValueError("원래 ID 예약 근거 불일치: " + row["run_id"])
        records.append({**row, "execution_status": state, "requirements": requirements})
    attempted = sum(row["execution_status"] != "NOT_STARTED" for row in records)
    complete = sum(row["execution_status"] == "COMPLETE" for row in records)
    return {"scope": "MAIN_ORIGINAL_80_ATTEMPTS", "original_attempted": attempted,
            "original_completed": complete, "not_started": 80 - attempted,
            "all_original_attempts_recorded": attempted == 80,
            "requirement_fail_count": sum(value["status"] == "FAIL" for row in records for value in row["requirements"].values()),
            "runs": records}


def execute_one(directory, manifest, row, allow_world_load):
    """preflight보다 먼저 원래 시도를 예약한다. 실패 ID도 자동 재시도하지 않는다."""
    verify_frozen(manifest)
    claim = {"run_id": row["run_id"], "run_token": row["run_token"],
             "claimed_utc": datetime.now(timezone.utc).isoformat(), "pid": os.getpid(),
             "config_sha256": manifest["config_sha256"]}
    atomic_write_json(directory / "attempts" / (row["run_id"] + ".json"), claim)
    config = manifest["config"]
    args = SimpleNamespace(output_dir=directory / "runs" / row["run_id"], interface="vcan0",
                           host=config["host"], port=config["port"], rpc_timeout=config["rpc_timeout_s"],
                           exclusive_server=True, allow_world_load=allow_world_load, main_config=config,
                           original_main_run=True, variant=row["variant"], scenario=row["scenario"],
                           run_token=row["run_token"], planned_run=row,
                           fixture_sha256=manifest["fixture_sha256"][row["scenario"]])
    run_vehicle(args)
    return json.loads((args.output_dir / "result.json").read_text())


def run_campaign(directory, manifest, max_runs, allow_world_load):
    executed = 0
    halted = False
    with campaign_lock(directory):
        verify_frozen(manifest)
        existing = status(directory, manifest)
        for row in existing["runs"]:
            if row["execution_status"] != "NOT_STARTED":
                continue
            if executed >= max_runs:
                break
            result = execute_one(directory, manifest, {key: row[key] for key in manifest["runs"][0]}, allow_world_load)
            executed += 1
            # 요구사항 FAIL은 보존하고 계속하되 실행/증거/주행 전제 오류면 멈춘다.
            if (result["execution_status"] != "COMPLETE" or result["cleanup_status"] != "PASS"
                    or not result["checks"].get("evidence_valid") or result["checks"].get("operational_failures")):
                halted = True
                break
        summary = status(directory, manifest)
        summary.update(batch_attempted=executed, batch_halted=halted)
        # 조회용 목록만 교체한다. 원래 시도/결과/고정 설정은 덮어쓰지 않는다.
        temporary = directory / (".status-" + str(os.getpid()) + ".json")
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(summary, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, directory / "status.json")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "status", "run", "check"):
        item = sub.add_parser(name)
        item.add_argument("--output-dir", type=Path, required=True)
        if name in ("run", "check"):
            item.add_argument("--exclusive-server", action="store_true", required=True)
            item.add_argument("--allow-world-load", action="store_true")
        if name == "run":
            item.add_argument("--max-runs", type=int, default=1)
        if name == "check":
            item.add_argument("--variant", choices=("A", "B"), required=True)
            item.add_argument("--scenario", choices=("T-01", "T-02", "T-03", "T-04"), required=True)
    args = parser.parse_args()

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt("종료 신호")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        directory = project_output(args.output_dir)
        if args.command == "prepare":
            plan = prepare(directory)
            print(json.dumps({"prepared_original_ids": len(plan["runs"]), "output_dir": str(directory), "main_trials_executed": 0}))
        elif args.command == "check":
            config = load_config()
            run_vehicle(SimpleNamespace(output_dir=directory, interface="vcan0", host=config["host"], port=config["port"],
                        rpc_timeout=config["rpc_timeout_s"], exclusive_server=True, allow_world_load=args.allow_world_load,
                        main_config=config, original_main_run=False, variant=args.variant, scenario=args.scenario,
                        fixture_sha256=fixture_digest(args.scenario)))
            result = json.loads((directory / "result.json").read_text())
            return 0 if result["status"] == "PASS" else 1
        else:
            plan = json.loads((directory / "manifest.json").read_text())
            if args.command == "status":
                summary = status(directory, plan)
            else:
                if not 1 <= args.max_runs <= 80:
                    raise ValueError("max-runs는1~80이어야 합니다")
                summary = run_campaign(directory, plan, args.max_runs, args.allow_world_load)
            print(json.dumps({key: value for key, value in summary.items() if key != "runs"}, ensure_ascii=False))
            if summary.get("batch_halted"):
                return 1
    except (OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("중단했습니다. 같은 계획의status를 조회하고 이미시도한 ID를 재사용하지 않습니다.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
