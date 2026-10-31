#!/usr/bin/env python3
"""독립 CAN 요청을 실제 CARLA 제동과 연결하는 G3 최소 실행기다.

송신 5개 정상/5개 정지/10개 정상 복원은 연결 확인용 입력이다.
거리 판단 SUT, A/B 비교, 전체 기동 상태 기계와 본시험은 실행하지 않는다.
전용 빈 서버에서 자신이 만든 actor만 제거하고 설정과 날씨를 복구한다.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import select
import signal
import socket
import struct
import subprocess
import sys
import time
import traceback


# 외부 PYTHONPATH는 차단한 채 이 저장소의 코드만 명시적으로 불러온다.
REPOSITORY = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY))
from tools import g2_carla_smoke as g2
from tools.g3_adapter_core import AdapterCallError, BrakeAdapterCore, G3InputError
from tools.g3_request_smoke import frame_fields, inspect_link, open_bus, write_json
from tools.g3_integration_oracle import evaluate_integration


SCOPE = "G3_CAN_TO_CARLA_SMOKE_ONLY"
EXIT_CODES = {"PASS": 0, "FAIL": 1, "ENV_ERROR": 2, "TOOL_ERROR": 3,
              "INPUT_ERROR": 4, "INTERRUPTED": 130}


class RunError(RuntimeError):
    """실행 전제, 시험 입력과 도구 오류의 분류를 유지한다."""

    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


def final_status(execution_status: str, checks: dict, cleanup_errors: list[str]) -> str:
    """관측된 FAIL은 종료 오류로 감추지 않고 통과에는 모든 근거를 요구한다."""
    if checks.get("failures"):
        return "FAIL"
    if execution_status != "COMPLETE":
        return execution_status
    if cleanup_errors or not checks.get("all_checks_passed"):
        return "TOOL_ERROR"
    return "PASS"


def worker_failure(output: Path, role: str, code: int) -> RunError:
    try:
        result = json.loads((output / f"{role}_result.json").read_text())
        status = result["status"]
        if status not in ("ENV_ERROR", "TOOL_ERROR", "INPUT_ERROR", "INTERRUPTED"):
            status = "TOOL_ERROR"
        if EXIT_CODES[status] != code:
            status = "TOOL_ERROR"
        return RunError(status, f"{role}: {result.get('error', result['status'])}")
    except (OSError, ValueError, KeyError):
        return RunError("TOOL_ERROR", f"{role} 종료 근거 없음: {code}")


def read_optional_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def check_worker_record(role: str, pid: int, code: int | None, record: dict) -> None:
    """실제 종료코드와 worker가 남긴 역할, PID 및 성공 선언을 대조한다."""
    if (record.get("pid") != pid or record.get("role") != role
            or record.get("exit_code") != code):
        raise RunError("TOOL_ERROR", role + ": 프로세스 또는 종료코드 기록 불일치")
    if record.get("status") == "COMPLETE" and code == 0:
        return
    status = record.get("status")
    if status not in ("ENV_ERROR", "TOOL_ERROR", "INPUT_ERROR", "INTERRUPTED") or EXIT_CODES[status] != code:
        status = "TOOL_ERROR"
    raise RunError(status, role + ": " + str(record.get("error", record.get("status"))))


def run(args) -> int:
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    metadata = {"scope": SCOPE, "baseline": "v1.0", "run_id": output.name,
                "run_token": secrets.randbits(32), "coordinator_pid": os.getpid(),
                "started_utc": datetime.now(timezone.utc).isoformat(),
                "execution_status": "ENV_ERROR", "fixture_sends_complete": False,
                "observation_window_complete": False, "full_g4_verified": False,
                "main_trials_executed": 0, "request_source": "G3 연결 확인 입력; SUT 출력 아님",
                "arming_scope": "차량 준비 후 G3 연결 입력 시작. 거리 입력 SUT의 기동/arm을 검증하지 않음",
                "phase_host_limit_seconds": 10.0, "command_arguments": sys.argv[1:]}
    world = actor = original_settings = original_weather = bus = core = None
    settings_changed = weather_changed = False
    children, handles, commands = {}, [], []
    cleanup_errors, samples, adapter_events, adapter_rx = [], [], [], []
    streams = {name: (output / (name + ".jsonl")).open("x", encoding="utf-8")
               for name in ("coordinator_events", "vehicle_states", "adapter_events", "adapter_rx")}

    def emit(name, row):
        streams[name].write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        streams[name].flush()

    def event(kind, **fields):
        emit("coordinator_events", {"kind": kind, "host_monotonic_ns": time.monotonic_ns(), **fields})

    def start_worker(role):
        argv = [sys.executable, "-I", str(REPOSITORY / "tools/g3_integration_can.py"),
                "--worker", role, "--interface", args.interface, "--output-dir", str(output),
                "--run-token", str(metadata["run_token"])]
        stderr = (output / f"{role}_stderr.txt").open("x", encoding="utf-8")
        handles.append(stderr)
        child = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=stderr)
        children[role] = child
        metadata.setdefault("worker_pids", {})[role] = child.pid
        commands.append({"role": role, "pid": child.pid, "argv": argv})

    def check_workers():
        for role, child in children.items():
            code = child.poll()
            if code is not None and (role == "observer" or code != 0):
                raise worker_failure(output, role, code)

    def receive_available():
        while True:
            try:
                raw = bus.recv(72)
            except BlockingIOError:
                break
            stamp = time.monotonic_ns()
            row = {"event": "rx", "pid": os.getpid(), "actor_id": actor.id,
                   "host_monotonic_ns": stamp, "raw_frame_hex": raw.hex()}
            try:
                row.update(frame_fields(raw))
            except ValueError as exc:
                row["decode_error"] = str(exc)
            adapter_rx.append(row)
            emit("adapter_rx", row)
            count = len(core.events)
            try:
                core.on_frame(raw, received_ns=stamp)
            finally:
                for item in core.events[count:]:
                    adapter_events.append(item)
                    emit("adapter_events", item)
            if len(adapter_rx) > 20:
                raise RunError("INPUT_ERROR", "지정한 20개보다 많은 요청을 관측했습니다")

    try:
        metadata["git_commit"] = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPOSITORY, capture_output=True,
            text=True, check=True).stdout.strip()
        source_names = ("g3_carla_smoke.py", "g3_integration_can.py", "g3_integration_oracle.py",
                        "g3_adapter_core.py", "g3_request_smoke.py", "g2_carla_smoke.py")
        metadata["source_sha256"] = {name: hashlib.sha256((REPOSITORY / "tools" / name).read_bytes()).hexdigest()
                                     for name in source_names}
        metadata["python_version"] = sys.version
        write_json(output / "metadata_started.json", metadata)
        metadata["interface"] = inspect_link(args.interface, output)
        import carla

        client = carla.Client(args.host, args.port)
        client.set_timeout(args.rpc_timeout)
        metadata.update(client_version=client.get_client_version(), server_version=client.get_server_version(),
                        host=args.host, port=args.port, exclusive_server_asserted=args.exclusive_server)
        if metadata["client_version"] != "0.9.15" or metadata["server_version"] != "0.9.15":
            raise RunError("ENV_ERROR", "서버와 client가 모두 정확히 0.9.15여야 합니다")
        world = client.get_world()
        g2.check_empty(world)
        if world.get_settings().synchronous_mode:
            raise RunError("ENV_ERROR", "이미 동기 모드인 서버는 사용하지 않습니다")
        metadata["initial_map"] = world.get_map().name
        if metadata["initial_map"].rsplit("/", 1)[-1] != "Town04":
            if not args.allow_world_load:
                raise RunError("ENV_ERROR", "Town04 로드에는 --allow-world-load가 필요합니다")
            event("load_world_begin")
            world = client.load_world("Town04")
            metadata["map_load_performed"] = True
            metadata["map_restoration"] = "명시 허용한 전용 맵 로드는 원래 맵으로 복구하지 않음"
        g2.check_empty(world)
        original_settings, original_weather = world.get_settings(), world.get_weather()
        settings = world.get_settings()
        metadata["original_settings"] = str(original_settings)
        settings.synchronous_mode, settings.fixed_delta_seconds = True, 0.05
        settings.substepping, settings.max_substep_delta_time, settings.max_substeps = True, 0.01, 10
        settings_changed = True
        world.apply_settings(settings)
        weather_changed = True
        world.set_weather(carla.WeatherParameters.ClearNoon)
        metadata["test_settings"] = str(settings)
        road_map = world.get_map()
        spawns = road_map.get_spawn_points()
        candidates = [(i, corridor) for i, spawn in enumerate(spawns)
                      if (corridor := g2.straight_corridor(road_map, spawn, carla))]
        if not candidates:
            raise RunError("ENV_ERROR", "100 m 평탄 직선 후보가 없습니다")
        index, corridor = candidates[0]
        blueprint = world.get_blueprint_library().find("vehicle.tesla.model3")
        blueprint.set_attribute("role_name", "g3_can_stop_smoke")
        blueprint.set_attribute("sticky_control", "true")
        actor = world.try_spawn_actor(blueprint, spawns[index])
        if actor is None:
            raise RunError("ENV_ERROR", "차량 생성 실패")
        if actor.attributes.get("sticky_control", "").lower() != "true":
            raise RunError("ENV_ERROR", "sticky_control=true가 유지되지 않았습니다")
        actor.set_autopilot(False)
        metadata.update(actor_id=actor.id, map=road_map.name, vehicle_blueprint=actor.type_id,
                        spawn_index=index, spawn_transform=g2.transform_dict(spawns[index]), corridor=corridor,
                        weather="ClearNoon", vehicle_physics=str(actor.get_physics_control()),
                        ackermann_controller_settings=str(actor.get_ackermann_controller_settings()),
                        spawn_scope="G3 연결 후보; 본시험 고정 좌표로 승인한 것은 아님")
        bus = open_bus(args.interface)
        bus.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FILTER, struct.pack("=II", 0x200, 0x7FF))
        bus.setblocking(False)
        for role in ("observer", "sender"):
            start_worker(role)
        ready_deadline = time.monotonic_ns() + 3_000_000_000
        while not all((output / f"{r}_ready.json").exists() for r in children):
            check_workers()
            if time.monotonic_ns() >= ready_deadline:
                raise RunError("ENV_ERROR", "CAN worker 준비 시간 초과")
            time.sleep(0.01)
        previous = world.get_snapshot()
        next_tick = time.monotonic_ns()
        metadata["preparation_started_monotonic_ns"] = next_tick
        metadata["preparation_deadline_monotonic_ns"] = next_tick + 30_000_000_000

        def tick(phase, control):
            nonlocal previous, next_tick
            remaining = (next_tick - time.monotonic_ns()) / 1e9
            if remaining > 0:
                time.sleep(remaining)
            begin = time.monotonic_ns()
            if control == "brake":
                g2.apply_brake_control(client, actor, carla)
            elif control == "drive":
                actor.apply_ackermann_control(carla.VehicleAckermannControl(
                    steer=0.0, speed=5.0 / 3.6, acceleration=0.0, jerk=0.0))
            control_done = time.monotonic_ns()
            frame = world.tick(args.rpc_timeout)
            snapshot = world.get_snapshot()
            observed = time.monotonic_ns()
            velocity, applied = actor.get_velocity(), actor.get_control()
            row = {"phase": phase, "frame": snapshot.frame,
                   "simulation_time_s": snapshot.timestamp.elapsed_seconds,
                   "simulation_delta_s": snapshot.timestamp.delta_seconds,
                   "host_monotonic_ns": observed, "tick_begin_monotonic_ns": control_done,
                   "tick_done_monotonic_ns": observed, "control_begin_monotonic_ns": begin,
                   "control_done_monotonic_ns": control_done, "scheduled_tick_monotonic_ns": next_tick,
                   "schedule_lateness_ns": max(0, begin - next_tick), "actor_id": actor.id,
                   "control_source": control, "velocity_mps": {"x": velocity.x, "y": velocity.y, "z": velocity.z},
                   "speed_mps": math.hypot(velocity.x, velocity.y),
                   "transform": g2.transform_dict(actor.get_transform()),
                   "applied_control": {"throttle": applied.throttle, "brake": applied.brake,
                                       "steer": applied.steer, "hand_brake": applied.hand_brake,
                                       "reverse": applied.reverse, "gear": applied.gear}}
            samples.append(row)
            emit("vehicle_states", row)
            if frame != snapshot.frame or snapshot.frame != previous.frame + 1:
                raise RunError("TOOL_ERROR", "동기 frame 연속성 불일치")
            if abs(snapshot.timestamp.elapsed_seconds - previous.timestamp.elapsed_seconds - 0.05) > 1e-6:
                raise RunError("TOOL_ERROR", "시뮬레이션 간격 불일치")
            previous = snapshot
            next_tick = max(next_tick + 50_000_000, begin + 50_000_000)
            return row

        for _ in range(20):
            check_workers()
            tick("settle", "brake")
            if time.monotonic_ns() >= metadata["preparation_deadline_monotonic_ns"]:
                raise RunError("ENV_ERROR", "초기 정착 중 30초 준비 시간 초과")
        drive_samples = []
        while True:
            check_workers()
            drive_samples.append(tick("drive", "drive"))
            prep = g2.assess_preparation(drive_samples, metadata["preparation_deadline_monotonic_ns"],
                                        time.monotonic_ns())
            metadata["preparation"] = prep
            if prep["status"] == "READY":
                break
            if prep["status"] == "TIMED_OUT":
                raise RunError("ENV_ERROR", "30초 안에 초기 5 km/h를 1초 유지하지 못했습니다")
        metadata["preparation_completed_monotonic_ns"] = prep["completed_monotonic_ns"]
        # 외부 요청이 준비 중 이미 쌓였다면 조용히 버리지 않고 시험을 중단한다.
        if select.select([bus], [], [], 0)[0]:
            raw = bus.recv(72)
            event("unexpected_prearm_frame", raw_frame_hex=raw.hex())
            raise RunError("INPUT_ERROR", "G3 입력 시작 전 다른 요청이 관측됐습니다")
        core = BrakeAdapterCore(actor_id=actor.id, run_token=metadata["run_token"],
                                apply_brake=lambda: g2.apply_brake_control(client, actor, carla))
        metadata["armed"] = {"host_monotonic_ns": time.monotonic_ns(), "frame": previous.frame,
                             "simulation_time_s": previous.timestamp.elapsed_seconds}
        event("g3_fixture_armed", **metadata["armed"])
        write_json(output / "sender_start.json", metadata["armed"])
        phase_deadline = metadata["armed"]["host_monotonic_ns"] + 10_000_000_000
        metadata["g3_phase_deadline_monotonic_ns"] = phase_deadline
        first_apply_frame = first_stop_next_frame = None
        while True:
            check_workers()
            if time.monotonic_ns() >= phase_deadline:
                raise RunError("ENV_ERROR", "G3 관측 단계의 10초 호스트 제한 초과")
            timeout = max(0.0, min(0.01, (next_tick - time.monotonic_ns()) / 1e9))
            if select.select([bus], [], [], timeout)[0]:
                receive_available()
            if core.stop_latched and first_stop_next_frame is None:
                first_stop_next_frame = previous.frame + 1
            if time.monotonic_ns() < next_tick:
                continue
            row = tick("g3", "latched_can" if core.stop_latched else "drive")
            if time.monotonic_ns() >= phase_deadline:
                raise RunError("ENV_ERROR", "G3 tick 반환 후 호스트 제한 시간 초과")
            if first_apply_frame is None and core.stop_latched and g2.brake_applied(row):
                first_apply_frame = row["frame"]
                event("brake_first_applied", frame=row["frame"], simulation_time_s=row["simulation_time_s"])
            target = (first_apply_frame + 40 if first_apply_frame is not None else
                      first_stop_next_frame + 44 if first_stop_next_frame is not None else None)
            if target is not None and row["frame"] >= target:
                metadata["observation_window_complete"] = True
                break
        # 송신을 다 읽었는지 최종 확인한 뒤 독립 관측기를 정상 종료한다.
        receive_available()
        sender_code = children["sender"].wait(timeout=2)
        if sender_code:
            raise worker_failure(output, "sender", sender_code)
        sender_result = json.loads((output / "sender_result.json").read_text())
        metadata["fixture_sends_complete"] = sender_result.get("status") == "COMPLETE" and sender_result.get("sent_frames") == 20
        metadata["execution_status"] = "COMPLETE"
    except (Exception, KeyboardInterrupt) as exc:
        metadata.update(execution_status=exc.status if isinstance(exc, RunError) else
                        "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else
                        "INPUT_ERROR" if isinstance(exc, G3InputError) else
                        "TOOL_ERROR" if isinstance(exc, AdapterCallError) else
                        "ENV_ERROR" if isinstance(exc, (OSError, RuntimeError, ImportError, subprocess.TimeoutExpired)) else "TOOL_ERROR",
                        error=str(exc), error_type=type(exc).__name__)
        (output / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
    finally:
        for role, child in children.items():
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    child.kill()
                    try:
                        child.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        cleanup_errors.append(role + ": 강제 종료 대기 초과")
                    cleanup_errors.append(role + ": 종료 유예 초과")
            metadata[role + "_exit_code"] = child.poll()
            try:
                worker_result = json.loads((output / f"{role}_result.json").read_text())
                metadata.setdefault("worker_results", {})[role] = worker_result
                try:
                    check_worker_record(role, child.pid, child.poll(), worker_result)
                except RunError as exc:
                    metadata.setdefault("worker_errors", []).append({"role": role, "status": exc.status, "error": str(exc)})
                    if metadata["execution_status"] == "COMPLETE":
                        metadata["execution_status"] = exc.status
            except (OSError, ValueError):
                cleanup_errors.append(role + ": 종료 결과를 읽지 못했습니다")
        if bus is not None:
            bus.close()
        if actor is not None:
            try:
                metadata["actor_destroyed"] = bool(actor.destroy())
                if not metadata["actor_destroyed"]:
                    cleanup_errors.append("actor 제거 응답 false")
            except Exception as exc:
                cleanup_errors.append("actor: " + str(exc))
        if world is not None and weather_changed and original_weather is not None:
            try:
                world.set_weather(original_weather)
                metadata["weather_restored"] = True
            except Exception as exc:
                cleanup_errors.append("weather: " + str(exc))
        if world is not None and settings_changed and original_settings is not None:
            try:
                world.apply_settings(original_settings)
                metadata["settings_restored"] = True
                metadata["post_cleanup"] = {"synchronous_mode": world.get_settings().synchronous_mode,
                                            "fixed_delta_seconds": world.get_settings().fixed_delta_seconds,
                                            "remaining_relevant_actors": [{"id": a.id, "type_id": a.type_id}
                                              for a in world.get_actors() if a.type_id.startswith(
                                                  ("vehicle.", "walker.", "sensor.", "controller."))]}
                if metadata["post_cleanup"]["synchronous_mode"] or metadata["post_cleanup"]["remaining_relevant_actors"]:
                    cleanup_errors.append("복구 후 상태 불일치")
            except Exception as exc:
                cleanup_errors.append("settings: " + str(exc))
        for stream in streams.values():
            stream.close()
        for handle in handles:
            handle.close()
        metadata.update(finished_utc=datetime.now(timezone.utc).isoformat(), cleanup_errors=cleanup_errors)
        write_json(output / "commands.json", commands)
        try:
            checks = evaluate_integration(metadata, read_optional_jsonl(output / "input_events.jsonl"),
                                          read_optional_jsonl(output / "can_observer.jsonl"), adapter_rx,
                                          adapter_events, samples)
        except Exception as exc:
            checks = {"all_checks_passed": False, "failures": [], "oracle_error": str(exc)}
            (output / "oracle_error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            if metadata["execution_status"] == "COMPLETE":
                metadata["execution_status"] = "TOOL_ERROR"
        write_json(output / "metadata.json", metadata)
        result = {"gate": "G3", "scope": SCOPE, "execution_status": metadata["execution_status"],
                  "cleanup_status": "FAIL" if cleanup_errors else "PASS", "checks": checks,
                  "status": final_status(metadata["execution_status"], checks, cleanup_errors),
                  "main_trials_executed": 0, "full_g4_verified": False}
        write_json(output / "result.json", result)
    print(json.dumps({"status": result["status"], "scope": SCOPE, "output_dir": str(output)}))
    return EXIT_CODES[result["status"]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interface", default="vcan0")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--exclusive-server", action="store_true", required=True,
                        help="다른 제어/tick 프로그램이 없는 전용 서버임을 명시")
    parser.add_argument("--allow-world-load", action="store_true", help="빈 서버의 Town04 로드 허용")
    parser.add_argument("--rpc-timeout", type=float, default=60.0)
    args = parser.parse_args()
    if not 1 <= args.port <= 65534 or not math.isfinite(args.rpc_timeout) or args.rpc_timeout <= 0:
        parser.error("유효한 포트와 양수 RPC 제한 시간이 필요합니다")

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt("종료 신호")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        return run(args)
    except FileExistsError:
        print("기존 증거 폴더는 사용하지 않습니다. 새 run ID를 사용하세요.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
