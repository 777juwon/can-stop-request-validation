#!/usr/bin/env python3
"""G2 standalone CARLA feasibility check, not a thesis scenario or CAN test.

Run only against a dedicated server without another ticking/controlling client.
Only the actor created here is destroyed. An explicitly allowed map load cannot
be undone; settings and weather on the tested world are restored on exit.
CARLA imports are deferred so observation rules can be tested without CARLA.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback
from typing import Callable, Iterable


VERSION = "0.9.15"
STEP = 0.05
TARGET_MPS = 5.0 / 3.6
PREPARATION_SECONDS = 30.0


def held_interval(
    samples: Iterable[dict], predicate: Callable[[dict], bool], duration: float,
    *, start: float = -math.inf, end: float = math.inf,
) -> dict | None:
    """Require consecutive frames at 0.05 s, using first-to-last sample time.

    Missing frames, nonfinite values and simulation-time discontinuities break
    continuity. A 0.5 s hold needs 11 samples, not 10 sample counts * 0.05 s.
    """
    first = previous = None
    count = 0
    for sample in samples:
        stamp = sample["simulation_time_s"]
        speed = sample["speed_mps"]
        valid = (math.isfinite(stamp) and math.isfinite(speed) and speed >= 0
                 and start <= stamp <= end and predicate(sample))
        contiguous = previous is not None and (
            sample["frame"] == previous["frame"] + 1
            and abs(stamp - previous["simulation_time_s"] - STEP) <= 1e-6
        )
        if not valid:
            first = previous = None
            count = 0
            continue
        if not contiguous:
            first = sample
            count = 0
        count += 1
        previous = sample
        if stamp - first["simulation_time_s"] >= duration - 1e-9:
            return {
                "first_frame": first["frame"], "last_frame": sample["frame"],
                "first_simulation_time_s": first["simulation_time_s"],
                "last_simulation_time_s": stamp, "sample_count": count,
            }
    return None


def brake_applied(sample: dict) -> bool:
    control = sample["applied_control"]
    return (control["brake"] >= 0.999 and control["throttle"] <= 0.001
            and abs(control["steer"]) <= 0.001 and not control["hand_brake"])


def assess_motion(samples: list[dict]) -> dict:
    drive = [s for s in samples if s["phase"] == "drive"]
    brake = [s for s in samples if s["phase"] == "brake"]
    stable = held_interval(drive, lambda s: 4.5 <= s["speed_mps"] * 3.6 <= 5.5, 1.0)
    applied = next((s for s in brake if brake_applied(s)), None)
    stopped = None
    if applied:
        stopped = held_interval(
            brake, lambda s: s["speed_mps"] <= 0.1 and brake_applied(s), 0.5,
            start=applied["simulation_time_s"],
            end=applied["simulation_time_s"] + 2.0 + 1e-9,
        )
    return {
        "actual_motion_observed": any(s["speed_mps"] > 0.1 for s in drive),
        "initial_5kmh_held_1s": stable,
        "first_brake_applied": None if applied is None else {
            "frame": applied["frame"],
            "simulation_time_s": applied["simulation_time_s"],
            "host_monotonic_ns": applied["host_monotonic_ns"],
        },
        "stop_held_0_5s_within_2s": stopped,
        "scope": "G2 standalone only; no CAN, SUT or main-trial requirements verified",
    }


def assess_preparation(samples: list[dict], deadline_ns: int, checked_ns: int) -> dict:
    """A tick started on time cannot establish readiness after the host deadline."""
    stable = held_interval(samples, lambda s: 4.5 <= s["speed_mps"] * 3.6 <= 5.5, 1.0)
    ready = stable is not None and checked_ns <= deadline_ns
    return {
        "status": "READY" if ready else "TIMED_OUT" if checked_ns >= deadline_ns else "PENDING",
        "deadline_monotonic_ns": deadline_ns,
        "checked_monotonic_ns": checked_ns,
        "completed_monotonic_ns": checked_ns if ready else None,
        "last_observation_monotonic_ns": samples[-1]["host_monotonic_ns"] if samples else None,
        "observed_stable_interval": stable,
        "deadline_overrun_ns": max(0, checked_ns - deadline_ns),
    }


def classify_result(execution_status: str, motion_status: str, cleanup_errors: list[str]) -> dict:
    """Keep established motion failures even if cleanup also fails."""
    cleanup_status = "FAIL" if cleanup_errors else "PASS"
    if motion_status == "FAIL":
        status = "FAIL"
    elif execution_status != "COMPLETE":
        status = execution_status
    elif motion_status != "PASS" or cleanup_errors:
        status = "ENV_ERROR"
    else:
        status = "PASS"
    return {"status": status, "execution_status": execution_status,
            "motion_status": motion_status, "cleanup_status": cleanup_status}


def json_write(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def transform_dict(transform) -> dict:
    return {
        "x": transform.location.x, "y": transform.location.y,
        "z": transform.location.z, "pitch": transform.rotation.pitch,
        "yaw": transform.rotation.yaw, "roll": transform.rotation.roll,
    }


def check_empty(world) -> None:
    occupied = [a for a in world.get_actors()
                if a.type_id.startswith(("vehicle.", "walker.", "sensor.", "controller."))]
    if occupied:
        raise RuntimeError("Refusing occupied world; existing actor IDs: "
                           + ",".join(str(a.id) for a in occupied))


def straight_corridor(road_map, spawn, carla) -> dict | None:
    """Conservative geometric candidate check, not obstacle-distance evidence."""
    waypoint = road_map.get_waypoint(spawn.location, lane_type=carla.LaneType.Driving)
    if waypoint is None or waypoint.is_junction:
        return None
    origin = waypoint.transform
    angle = math.radians(origin.rotation.yaw)
    start_z = origin.location.z
    for _ in range(50):
        choices = waypoint.next(2.0)
        if len(choices) != 1:
            return None
        waypoint = choices[0]
        location = waypoint.transform.location
        yaw_delta = (waypoint.transform.rotation.yaw - origin.rotation.yaw + 180) % 360 - 180
        lateral = -(location.x - origin.location.x) * math.sin(angle) + (
            location.y - origin.location.y) * math.cos(angle)
        if (waypoint.is_junction or abs(yaw_delta) > 1.0
                or abs(location.z - start_z) > 0.25 or abs(lateral) > 0.5):
            return None
    return {"checked_distance_m": 100.0, "end": transform_dict(waypoint.transform),
            "max_allowed_heading_change_deg": 1.0, "max_allowed_height_change_m": 0.25,
            "max_allowed_lateral_offset_m": 0.5}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--host", default="127.0.0.1")
    result.add_argument("--port", type=int, default=2000)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--exclusive-server", action="store_true", required=True,
                        help="Assert this is a dedicated server with no other tick/control clients")
    result.add_argument("--allow-world-load", action="store_true",
                        help="Allow loading Town04 on an otherwise empty dedicated server")
    result.add_argument("--spawn-index", type=int,
                        help="Optional fixed index in Town04 recommended spawn points")
    result.add_argument("--rpc-timeout", type=float, default=60.0)
    return result


def run(args: argparse.Namespace) -> int:
    args.output_dir.mkdir(parents=True, exist_ok=False)
    result = {"gate": "G2", "status": "ENV_ERROR", "scope": "standalone CARLA only",
              "execution_status": "ENV_ERROR", "motion_status": "INCONCLUSIVE",
              "baseline": "v1.0", "cleanup_errors": [], "map_load_performed": False}
    world = actor = original_settings = original_weather = None
    settings_changed = weather_changed = False
    samples = []
    exit_code = 2
    log = (args.output_dir / "vehicle_states.jsonl").open("x", encoding="utf-8")
    events = (args.output_dir / "events.jsonl").open("x", encoding="utf-8")

    def event(kind: str, **fields) -> None:
        events.write(json.dumps({"kind": kind, "host_monotonic_ns": time.monotonic_ns(),
                                 **fields}, allow_nan=False) + "\n")
        events.flush()

    try:
        import carla

        script_path = Path(__file__).resolve()
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=script_path.parent.parent,
            capture_output=True, text=True, check=False,
        )
        result.update({
            "git_commit": commit.stdout.strip() if commit.returncode == 0 else None,
            "tool_sha256": hashlib.sha256(script_path.read_bytes()).hexdigest(),
            "command_arguments": sys.argv[1:],
        })
        client = carla.Client(args.host, args.port)
        client.set_timeout(args.rpc_timeout)
        result.update({"client_version": client.get_client_version(),
                       "server_version": client.get_server_version(),
                       "python_version": sys.version, "host": args.host, "port": args.port,
                       "exclusive_server_asserted": args.exclusive_server,
                       "fixed_delta_seconds": STEP, "target_speed_mps": TARGET_MPS})
        if result["client_version"] != VERSION or result["server_version"] != VERSION:
            raise RuntimeError("Expected exact CARLA server/client version 0.9.15")
        world = client.get_world()
        check_empty(world)
        if world.get_settings().synchronous_mode:
            raise RuntimeError("Refusing world already in synchronous mode; possible other coordinator")
        result["initial_map"] = world.get_map().name
        if world.get_map().name.rsplit("/", 1)[-1] != "Town04":
            if not args.allow_world_load:
                raise RuntimeError("Town04 is required; explicit --allow-world-load needed")
            event("load_world_begin", map="Town04")
            world = client.load_world("Town04")
            result["map_load_performed"] = True
            result["map_restoration"] = "not restored; dedicated-world load explicitly permitted"
            event("load_world_done", map=world.get_map().name)
        check_empty(world)
        original_settings = world.get_settings()
        original_weather = world.get_weather()
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = STEP
        settings.substepping = True
        settings.max_substep_delta_time = 0.01
        settings.max_substeps = 10
        result["original_settings"] = str(original_settings)
        result["test_settings"] = str(settings)
        settings_changed = True
        world.apply_settings(settings)
        weather_changed = True
        world.set_weather(carla.WeatherParameters.ClearNoon)

        road_map = world.get_map()
        spawns = road_map.get_spawn_points()
        candidates = []
        indices = range(len(spawns)) if args.spawn_index is None else [args.spawn_index]
        for index in indices:
            if index < 0 or index >= len(spawns):
                raise RuntimeError("Spawn index outside map spawn point list")
            corridor = straight_corridor(road_map, spawns[index], carla)
            if corridor:
                candidates.append((index, corridor))
        result["straight_candidate_indices"] = [i for i, _ in candidates]
        if not candidates:
            raise RuntimeError("No selected spawn passes 100 m flat straight corridor check")
        index, corridor = candidates[0]
        blueprint = world.get_blueprint_library().find("vehicle.tesla.model3")
        blueprint.set_attribute("role_name", "g2_standalone_smoke")
        actor = world.try_spawn_actor(blueprint, spawns[index])
        if actor is None:
            raise RuntimeError("Vehicle spawn failed; no actor created")
        result.update({"map": road_map.name, "vehicle_blueprint": actor.type_id,
                       "actor_id": actor.id, "spawn_index": index,
                       "spawn_transform": transform_dict(spawns[index]), "corridor": corridor,
                       "weather": "ClearNoon", "vehicle_physics": str(actor.get_physics_control()),
                       "ackermann_controller_settings": str(actor.get_ackermann_controller_settings()),
                       "spawn_scope": "G2 feasibility candidate, not frozen main-trial coordinates"})
        actor.set_autopilot(False)
        json_write(args.output_dir / "metadata.json", result)
        event("vehicle_spawned", actor_id=actor.id, spawn_index=index)

        previous = world.get_snapshot()
        next_tick_ns = time.monotonic_ns()
        preparation_deadline = next_tick_ns + int(PREPARATION_SECONDS * 1e9)
        result["preparation_started_monotonic_ns"] = next_tick_ns
        result["preparation_deadline_monotonic_ns"] = preparation_deadline
        drive_samples = []

        def tick(phase: str, command: dict) -> dict:
            nonlocal previous, next_tick_ns
            wait_s = (next_tick_ns - time.monotonic_ns()) / 1e9
            if wait_s > 0:
                time.sleep(wait_s)
            begin = time.monotonic_ns()
            if command["type"] == "ackermann":
                actor.apply_ackermann_control(carla.VehicleAckermannControl(
                    steer=0.0, speed=TARGET_MPS, acceleration=0.0, jerk=0.0))
            else:
                actor.apply_control(carla.VehicleControl(
                    throttle=0.0, brake=1.0, steer=0.0, hand_brake=False))
            control_done = time.monotonic_ns()
            frame = world.tick(args.rpc_timeout)
            snapshot = world.get_snapshot()
            observed_ns = time.monotonic_ns()
            velocity = actor.get_velocity()
            control = actor.get_control()
            sample = {
                "phase": phase, "frame": snapshot.frame,
                "simulation_time_s": snapshot.timestamp.elapsed_seconds,
                "simulation_delta_s": snapshot.timestamp.delta_seconds,
                "host_monotonic_ns": observed_ns,
                "tick_begin_monotonic_ns": control_done, "tick_done_monotonic_ns": observed_ns,
                "control_begin_monotonic_ns": begin, "control_done_monotonic_ns": control_done,
                "scheduled_tick_monotonic_ns": next_tick_ns,
                "schedule_lateness_ns": max(0, begin - next_tick_ns),
                "actor_id": actor.id, "command": command,
                "velocity_mps": {"x": velocity.x, "y": velocity.y, "z": velocity.z},
                "speed_mps": math.hypot(velocity.x, velocity.y),
                "transform": transform_dict(actor.get_transform()),
                "applied_control": {"throttle": control.throttle, "brake": control.brake,
                                    "steer": control.steer, "hand_brake": control.hand_brake,
                                    "reverse": control.reverse, "gear": control.gear},
            }
            log.write(json.dumps(sample, allow_nan=False) + "\n")
            log.flush()
            samples.append(sample)
            if frame != snapshot.frame or snapshot.frame != previous.frame + 1:
                raise RuntimeError("Unexpected frame progression; another tick client or lost evidence")
            if abs(snapshot.timestamp.elapsed_seconds - previous.timestamp.elapsed_seconds - STEP) > 1e-6:
                raise RuntimeError("Unexpected simulation-time step")
            previous = snapshot
            # Keep every overrun visible, avoiding catch-up bursts of old slots.
            next_tick_ns = max(next_tick_ns + int(STEP * 1e9), begin + int(STEP * 1e9))
            return sample

        for _ in range(20):
            tick("settle", {"type": "vehicle_control", "throttle": 0, "brake": 1})
            result["preparation"] = assess_preparation([], preparation_deadline, time.monotonic_ns())
            if result["preparation"]["status"] == "TIMED_OUT":
                raise RuntimeError("30 s host preparation deadline exceeded during settling")
        while time.monotonic_ns() < preparation_deadline:
            sample = tick("drive", {"type": "ackermann", "speed_mps": TARGET_MPS, "steer": 0})
            drive_samples.append(sample)
            result["preparation"] = assess_preparation(
                drive_samples, preparation_deadline, time.monotonic_ns())
            if result["preparation"]["status"] == "TIMED_OUT":
                raise RuntimeError("30 s host preparation deadline exceeded after drive observation")
            if result["preparation"]["status"] == "READY":
                break
        else:
            result["preparation"] = assess_preparation(
                drive_samples, preparation_deadline, time.monotonic_ns())
            raise RuntimeError("Failed to hold 5.0 +/- 0.5 km/h for 1 s within 30 s host preparation")
        event("initial_speed_stable", frame=samples[-1]["frame"],
              simulation_time_s=samples[-1]["simulation_time_s"],
              completed_monotonic_ns=result["preparation"]["completed_monotonic_ns"],
              deadline_monotonic_ns=preparation_deadline)
        applied_time = None
        # 41 observations span 2.0 s. Allow extra first ticks only to diagnose
        # lack of applied control; they cannot extend an established stop window.
        for _ in range(45):
            sample = tick("brake", {"type": "vehicle_control", "throttle": 0, "brake": 1,
                                     "steer": 0, "hand_brake": False})
            if applied_time is None and brake_applied(sample):
                applied_time = sample["simulation_time_s"]
                event("brake_first_applied", frame=sample["frame"], simulation_time_s=applied_time)
            if applied_time is not None and sample["simulation_time_s"] >= applied_time + 2.0 - 1e-9:
                break
        result["motion_checks"] = assess_motion(samples)
        result["execution_status"] = "COMPLETE"
        checks = result["motion_checks"]
        passed = all(checks[k] for k in ("actual_motion_observed", "initial_5kmh_held_1s",
                                         "first_brake_applied", "stop_held_0_5s_within_2s"))
        result["motion_status"] = "PASS" if passed else "FAIL"
    except (Exception, KeyboardInterrupt) as exc:
        result["error_type"] = type(exc).__name__
        result["error"] = str(exc)
        result["motion_checks"] = assess_motion(samples)
        result["execution_status"] = "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "ENV_ERROR"
        (args.output_dir / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
    finally:
        if actor is not None:
            try:
                result["actor_destroyed"] = bool(actor.destroy())
                if not result["actor_destroyed"]:
                    result["cleanup_errors"].append("Actor destroy returned False")
            except Exception as exc:
                result["cleanup_errors"].append("actor: " + str(exc))
        if world is not None and original_weather is not None and weather_changed:
            try:
                world.set_weather(original_weather)
                result["weather_restored"] = True
            except Exception as exc:
                result["cleanup_errors"].append("weather: " + str(exc))
        if world is not None and original_settings is not None and settings_changed:
            try:
                world.apply_settings(original_settings)
                result["settings_restored"] = True
            except Exception as exc:
                result["cleanup_errors"].append("settings: " + str(exc))
        result.update(classify_result(result["execution_status"], result["motion_status"],
                                      result["cleanup_errors"]))
        exit_code = {"PASS": 0, "FAIL": 1, "ENV_ERROR": 2, "INTERRUPTED": 130}[result["status"]]
        result["observation_count"] = len(samples)
        if samples:
            result["max_schedule_lateness_ms"] = max(s["schedule_lateness_ns"] for s in samples) / 1e6
            result["max_tick_duration_ms"] = max(
                s["tick_done_monotonic_ns"] - s["tick_begin_monotonic_ns"] for s in samples) / 1e6
        event("finished", status=result["status"], cleanup_errors=result["cleanup_errors"])
        log.close()
        events.close()
        json_write(args.output_dir / "result.json", result)
    print(json.dumps({"status": result["status"], "output_dir": str(args.output_dir),
                      "scope": "G2 standalone only"}))
    return exit_code


def main() -> int:
    args = parser().parse_args()
    if not 1 <= args.port <= 65535 or args.rpc_timeout <= 0 or not math.isfinite(args.rpc_timeout):
        parser().error("port must be 1..65535 and rpc-timeout must be finite and positive")
    # SIGTERM from timeout wrappers should preserve evidence and run cleanup too.
    def terminated(_signum, _frame):
        raise KeyboardInterrupt("SIGTERM")
    signal.signal(signal.SIGTERM, terminated)
    try:
        return run(args)
    except FileExistsError:
        print("Output directory already exists; choose a new run ID", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
