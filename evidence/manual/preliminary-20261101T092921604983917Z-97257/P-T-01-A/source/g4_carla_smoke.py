#!/usr/bin/env python3
"""A 방식 거리 수신 중단에서 실제 CARLA 정지까지 연결하는 G4 실행기다.

정해진 T-03 입력 한 번만 실행한다. B 비교와 본시험 80회는 수행하지 않는다.
독립 송신기, 관측기와 SUT를 분리하고 여기서만 차량 제어와 tick을 소유한다.
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


# 외부 PYTHONPATH를 차단한 상태에서 저장소의 도구만 명시적으로 불러온다.
REPOSITORY = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY))
from tools import g2_carla_smoke as g2
from tools.g3_adapter_core import AdapterCallError, BrakeAdapterCore, G3InputError
from tools.g3_carla_smoke import RunError, final_status, read_optional_jsonl
from tools.g3_request_smoke import frame_fields, inspect_link, open_bus, write_json
from tools.g4_can_workers import atomic_write_json
from tools.g4_oracle import evaluate_g4


SCOPE = "G4_A_RX_TIMEOUT_MINIMUM_CHAIN_ONLY"
EXIT_CODES = {"PASS": 0, "FAIL": 1, "ENV_ERROR": 2, "TOOL_ERROR": 3,
              "INPUT_ERROR": 4, "SUT_ERROR": 5, "INTERRUPTED": 130}


def check_worker_record(role, pid, code, record):
    """G4의 SUT 오류와 실제 프로세스 종료 근거를 함께 확인한다."""
    if record.get("pid") != pid or record.get("role") != role or record.get("exit_code") != code:
        raise RunError("TOOL_ERROR", role + ": PID/역할/실제 종료코드 불일치")
    if record.get("status") == "COMPLETE" and code == 0:
        return
    status = record.get("status")
    if status not in ("ENV_ERROR", "TOOL_ERROR", "INPUT_ERROR", "SUT_ERROR", "INTERRUPTED") or EXIT_CODES[status] != code:
        status = "TOOL_ERROR"
    raise RunError(status, role + ": " + str(record.get("error", record.get("status"))))


def worker_failure(output, role, child):
    """조기 종료를 성공으로 상속하지 않고 기록된 오류 분류를 유지한다."""
    try:
        record = json.loads((output / f"{role}_result.json").read_text())
        check_worker_record(role, child.pid, child.poll(), record)
    except RunError as exc:
        return exc
    except (OSError, ValueError):
        return RunError("TOOL_ERROR", role + ": 조기 종료 근거 없음")
    return RunError("TOOL_ERROR", role + ": 예상하지 못한 조기 종료")


def select_trial_ready(drive_samples, t0_ns):
    """T0 전에 완료한 최근 1초의 실제 속도로만 시작 준비를 확인한다."""
    before_t0 = [row for row in drive_samples if row["host_monotonic_ns"] <= t0_ns]
    initial = before_t0[-21:]
    if len(initial) != 21 or any(not 4.5 <= row["speed_mps"] * 3.6 <= 5.5 for row in initial):
        raise RunError("ENV_ERROR", "T0 직전 초기 속도의 1초 유지가 충족되지 않았습니다")
    if any(right["frame"] != left["frame"] + 1
           or abs(right["simulation_time_s"] - left["simulation_time_s"] - .05) > 1e-6
           for left, right in zip(initial, initial[1:])):
        raise RunError("TOOL_ERROR", "T0 직전 초기 속도 표본이 연속하지 않습니다")
    return {key: initial[-1][key] for key in ("frame", "simulation_time_s", "host_monotonic_ns")}


def start_chain_workers(start_worker, wait_record, deadline):
    """최초 INIT 요청도 관측할 수 있도록 관측기 bind 완료를 먼저 기다린다."""
    for role in ("observer", "controller", "sender"):
        start_worker(role)
        wait_record(role + "_ready.json", deadline)


def run(args) -> int:
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    metadata = {"scope": SCOPE, "gate": "G4", "baseline": "v1.0", "variant": "A",
                "scenario": "T-03", "run_id": output.name, "run_token": secrets.randbits(32),
                "coordinator_pid": os.getpid(), "started_utc": datetime.now(timezone.utc).isoformat(),
                "execution_status": "ENV_ERROR", "fixture_sends_complete": False,
                "observation_window_complete": False, "main_trials_executed": 0,
                "command_arguments": sys.argv[1:],
                "scope_note": "기동/arm과 A의 거리 중단 한 번. 전체 A/B 검증이나 본시험이 아님"}
    world = actor = original_settings = original_weather = bus = core = None
    settings_changed = weather_changed = False
    children, handles, commands = {}, [], []
    cleanup_errors, samples, adapter_events, adapter_rx = [], [], [], []
    streams = {name: (output / (name + ".jsonl")).open("x", encoding="utf-8")
               for name in ("coordinator_events", "vehicle_states", "adapter_events",
                            "adapter_rx", "adapter_prearm_rx")}

    def emit(name, row):
        streams[name].write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        streams[name].flush()

    def event(kind, **fields):
        emit("coordinator_events", {"kind": kind, "host_monotonic_ns": time.monotonic_ns(), **fields})

    def start_worker(role):
        argv = [sys.executable, "-I", str(REPOSITORY / "tools/g4_can_workers.py"),
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
            if code is not None and (role != "sender" or code != 0):
                raise worker_failure(output, role, child)

    def signal_file(name):
        atomic_write_json(output / name, {"run_token": metadata["run_token"],
                                          "host_monotonic_ns": time.monotonic_ns()})

    def wait_record(name, deadline):
        while not (output / name).exists():
            check_workers()
            if time.monotonic_ns() >= deadline:
                raise RunError("ENV_ERROR", name + " 준비 시간 초과")
            time.sleep(.01)
        record = json.loads((output / name).read_text())
        if record.get("run_token") != metadata["run_token"]:
            raise RunError("TOOL_ERROR", name + " token 불일치")
        return record

    def receive_available(*, prearm=False):
        count = 0
        while True:
            try:
                raw = bus.recv(72)
            except BlockingIOError:
                return
            stamp = time.monotonic_ns()
            row = {"event": "rx", "pid": os.getpid(), "actor_id": actor.id,
                   "host_monotonic_ns": stamp, "raw_frame_hex": raw.hex()}
            try:
                row.update(frame_fields(raw))
            except ValueError as exc:
                row["decode_error"] = str(exc)
            if prearm:
                emit("adapter_prearm_rx", row)
            else:
                adapter_rx.append(row)
                emit("adapter_rx", row)
                index = len(core.events)
                try:
                    core.on_frame(raw, received_ns=stamp)
                finally:
                    for item in core.events[index:]:
                        adapter_events.append(item)
                        emit("adapter_events", item)
            count += 1
            if count > 5000:
                raise RunError("INPUT_ERROR", "한 번의 수신에서 지정 범위를 넘는 요청이 관측됐습니다")

    try:
        metadata["git_commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPOSITORY, text=True).strip()
        source_names = ("g4_carla_smoke.py", "g4_can_workers.py", "g4_controller_core.py", "g4_oracle.py",
                        "g3_adapter_core.py", "g3_carla_smoke.py", "g3_request_smoke.py",
                        "g3_integration_can.py", "g2_carla_smoke.py")
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
            raise RunError("ENV_ERROR", "서버와 client는 모두 정확히 0.9.15여야 합니다")
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
            metadata.update(map_load_performed=True, map_restoration="허용한 전용 맵 로드는 원래 맵으로 복구하지 않음")
        g2.check_empty(world)
        original_settings, original_weather = world.get_settings(), world.get_weather()
        settings = world.get_settings()
        metadata["original_settings"] = str(original_settings)
        settings.synchronous_mode, settings.fixed_delta_seconds = True, .05
        settings.substepping, settings.max_substep_delta_time, settings.max_substeps = True, .01, 10
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
        blueprint.set_attribute("role_name", "g4_distance_stop_smoke")
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
                        spawn_scope="G4 연결 후보; 본시험 고정 좌표 승인과 구분")
        bus = open_bus(args.interface)
        bus.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FILTER, struct.pack("=II", 0x200, 0x7FF))
        bus.setblocking(False)
        # INIT 동안 차량은 coordinator가 제동한다. 아직 G3 잠금 객체를 만들지 않는다.
        g2.apply_brake_control(client, actor, carla)
        metadata["preparation_started_monotonic_ns"] = time.monotonic_ns()
        deadline = metadata["preparation_started_monotonic_ns"] + 30_000_000_000
        metadata["preparation_deadline_monotonic_ns"] = deadline
        ready_deadline = min(deadline, time.monotonic_ns() + 3_000_000_000)
        start_chain_workers(start_worker, wait_record, ready_deadline)
        metadata["controller_input_ready"] = wait_record("controller_input_ready.json", deadline)
        signal_file("controller_arm.json")
        metadata["armed"] = wait_record("controller_armed.json", deadline)
        # arm 직후 정상 요청 송신 완료를 확인한 뒤 초기 큐를 근거로 남긴다.
        receive_available(prearm=True)
        core = BrakeAdapterCore(actor_id=actor.id, run_token=metadata["run_token"],
                                apply_brake=lambda: g2.apply_brake_control(client, actor, carla))
        metadata["adapter_active_ns"] = time.monotonic_ns()
        event("adapter_armed", arm_host_monotonic_ns=metadata["armed"]["host_monotonic_ns"])
        previous = world.get_snapshot()
        next_tick = time.monotonic_ns()

        def tick(phase, control):
            nonlocal previous, next_tick
            begin = time.monotonic_ns()
            if control == "brake":
                g2.apply_brake_control(client, actor, carla)
            elif control == "drive":
                actor.apply_ackermann_control(carla.VehicleAckermannControl(
                    steer=0., speed=5. / 3.6, acceleration=0., jerk=0.))
            control_done = time.monotonic_ns()
            frame = world.tick(args.rpc_timeout)
            snapshot = world.get_snapshot()
            velocity, applied = actor.get_velocity(), actor.get_control()
            observed = time.monotonic_ns()
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
            if abs(snapshot.timestamp.elapsed_seconds - previous.timestamp.elapsed_seconds - .05) > 1e-6:
                raise RunError("TOOL_ERROR", "시뮬레이션 간격 불일치")
            previous = snapshot
            next_tick = max(next_tick + 50_000_000, begin + 50_000_000)
            return row

        settle_count, trial_requested, trial_started = 0, False, False
        drive_samples = []
        first_applied = None
        while True:
            check_workers()
            now = time.monotonic_ns()
            if not trial_started and now >= deadline:
                raise RunError("ENV_ERROR", "30초 안에 준비와 T0 시작을 완료하지 못했습니다")
            if not trial_started and (output / "trial_started.json").exists():
                started = json.loads((output / "trial_started.json").read_text())
                if started.get("run_token") != metadata["run_token"]:
                    raise RunError("TOOL_ERROR", "trial 시작 token 불일치")
                metadata.update({key: started[key] for key in (
                    "t0_ns", "t0_done_ns", "trial_global_slot", "trial_first_scheduled_ns", "trial_end_ns")})
                if not trial_requested or not drive_samples:
                    raise RunError("INPUT_ERROR", "주행 준비 요청 전에 본 입력이 시작됐습니다")
                # T0가 tick 도중 시작돼도 경계 표본을 준비 완료로 소급하지 않는다.
                metadata["trial_ready"] = select_trial_ready(drive_samples, metadata["t0_ns"])
                if metadata["t0_ns"] >= deadline:
                    raise RunError("ENV_ERROR", "T0가 준비 기한을 넘었습니다")
                trial_started = True
                event("trial_started", t0_ns=metadata["t0_ns"])
            if trial_started and now >= metadata["trial_end_ns"] + 10_000_000_000:
                raise RunError("ENV_ERROR", "입력 종료 뒤 추가 관측의 10초 호스트 제한 초과")
            wait = max(0., min(.01, (next_tick - now) / 1e9))
            if select.select([bus], [], [], wait)[0]:
                receive_available()
            if time.monotonic_ns() < next_tick:
                continue
            phase = "g4" if trial_started else "settle" if settle_count < 20 else "drive"
            control = "latched_can" if core.stop_latched else "brake" if phase == "settle" else "drive"
            row = tick(phase, control)
            if phase == "settle":
                settle_count += 1
            elif phase == "drive":
                drive_samples.append(row)
                prep = g2.assess_preparation(drive_samples, deadline, time.monotonic_ns())
                metadata["preparation"] = prep
                if prep["status"] == "TIMED_OUT":
                    raise RunError("ENV_ERROR", "초기 속도 준비의 30초 기한 초과")
                if prep["status"] == "READY":
                    metadata.setdefault("preparation_completed_monotonic_ns", prep["completed_monotonic_ns"])
                    if not trial_requested:
                        signal_file("trial_requested.json")
                        trial_requested = True
            if trial_started and core.stop_latched and first_applied is None and g2.brake_applied(row):
                first_applied = row["frame"]
                event("brake_first_applied", frame=row["frame"], simulation_time_s=row["simulation_time_s"])
            if trial_started and time.monotonic_ns() >= metadata["trial_end_ns"] and children["sender"].poll() == 0:
                target = first_applied + 40 if first_applied is not None else None
                if target is None or row["frame"] >= target:
                    metadata["observation_window_complete"] = True
                    break
        # 마지막 주기 요청이 수신/차량 표본 뒤에 끼어들지 않도록 SUT부터 끝낸다.
        children["controller"].terminate()
        children["controller"].wait(timeout=2)
        record = json.loads((output / "controller_result.json").read_text())
        check_worker_record("controller", children["controller"].pid, children["controller"].poll(), record)
        receive_available()
        remaining = (next_tick - time.monotonic_ns()) / 1e9
        if remaining > 0:
            time.sleep(remaining)
        tick("g4", "latched_can" if core.stop_latched else "drive")
        sender_result = json.loads((output / "sender_result.json").read_text())
        metadata["fixture_sends_complete"] = sender_result.get("status") == "COMPLETE"
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
        # SUT를 먼저 멈추고 독립 관측기를 마지막에 종료한다.
        for role in ("controller", "sender", "observer"):
            if role not in children:
                continue
            child = children[role]
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
                record = json.loads((output / f"{role}_result.json").read_text())
                metadata.setdefault("worker_results", {})[role] = record
                check_worker_record(role, child.pid, child.poll(), record)
            except (OSError, ValueError, RunError) as exc:
                metadata.setdefault("worker_errors", []).append({"role": role, "error": str(exc)})
                if metadata["execution_status"] == "COMPLETE":
                    metadata["execution_status"] = exc.status if isinstance(exc, RunError) else "TOOL_ERROR"
        if bus is not None:
            bus.close()
        if actor is not None:
            try:
                metadata["actor_destroyed"] = bool(actor.destroy())
                if not metadata["actor_destroyed"]:
                    cleanup_errors.append("actor 제거 응답 false")
            except Exception as exc:
                cleanup_errors.append("actor: " + str(exc))
        if world is not None and weather_changed:
            try:
                world.set_weather(original_weather)
                metadata["weather_restored"] = True
            except Exception as exc:
                cleanup_errors.append("weather: " + str(exc))
        if world is not None and settings_changed:
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
            checks = evaluate_g4(metadata, read_optional_jsonl(output / "input_events.jsonl"),
                                 read_optional_jsonl(output / "can_observer.jsonl"),
                                 read_optional_jsonl(output / "sut_events.jsonl"), adapter_rx, adapter_events, samples)
        except Exception as exc:
            checks = {"all_checks_passed": False, "failures": [], "oracle_error": str(exc)}
            (output / "oracle_error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            if metadata["execution_status"] == "COMPLETE":
                metadata["execution_status"] = "TOOL_ERROR"
        write_json(output / "metadata.json", metadata)
        result = {"gate": "G4", "scope": SCOPE, "execution_status": metadata["execution_status"],
                  "cleanup_status": "FAIL" if cleanup_errors else "PASS", "checks": checks,
                  "status": final_status(metadata["execution_status"], checks, cleanup_errors),
                  "main_trials_executed": 0}
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
    parser.add_argument("--rpc-timeout", type=float, default=60.)
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
