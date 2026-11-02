#!/usr/bin/env python3
"""검토된 본시험 위치 로그로 CARLA 설명용 사진을 별도 생성한다.

차량 물리를 끄고 기록 위치를 배치한다. CAN/제어기/제동 시험의 재실행이
아니며 사진에 대응하는 속도와 제어값은 원본 로그의 값이다.
직접 시작한 서버만 종료하고 비정상 종료를 정상으로 바꾸지 않는다.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "analysis/main-20261102/analysis_manifest.json"
CAMPAIGN = ROOT / "runs/main-v1-20261101/runs"
SCOPE = "RECORDED_POSE_VISUALIZATION_ONLY"
SELECTIONS = (
    ("01-normal", "M-T-01-R01-A", 2., "정상 원거리 주행 위치"),
    ("02-near-before", "M-T-02-R01-B", 12., "근거리 요청 전 주행 위치"),
    ("03-near-stop", "M-T-02-R01-B", "stop_hold", "근거리 요청 후 정지 유지 완료 위치"),
    ("04-timeout-stop", "M-T-03-R01-B", "stop_hold", "거리 수신 중단 후 정지 유지 완료 위치"),
    ("05-repeat-A", "M-T-04-R01-A", 9., "반복 입력 복원 후 A의 계속 주행 위치"),
    ("06-repeat-B", "M-T-04-R01-B", 9., "반복 입력 복원 후 B의 정지 잠금 위치"),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def audit_inputs(expected):
    """이미 분석한 원본 전체를 대조한다. 불일치하면 촬영을 진행하지 않는다."""
    for relative, checksum in expected.items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or sha(path) != checksum:
            raise ValueError("원본 SHA 불일치: " + relative)
    return {"status": "PASS", "verified_files": len(expected)}


def selected_sample(meta, result, samples, selector):
    """호스트 시각으로 고른 위치와 원본 정지 판정 프레임을 구분한다."""
    rows = [s for s in samples if s["phase"] == "g4"
            and meta["t0_ns"] <= s["host_monotonic_ns"] <= meta["trial_end_ns"]]
    if selector == "stop_hold":
        if result["checks"]["requirements"]["R-07"]["status"] != "PASS":
            raise ValueError("원본 정지 유지 조건 미충족")
        frame = result["checks"]["metrics"]["stop_hold"]["last_frame"]
        row = next(s for s in rows if s["frame"] == frame)
        if row["speed_mps"] > .1 or row["applied_control"]["brake"] < .999:
            raise ValueError("정지 프레임과 실제 원본 상태 불일치")
    else:
        target = meta["t0_ns"] + int(selector * 1e9)
        row = next(s for s in rows if s["host_monotonic_ns"] >= target)
        if row["host_monotonic_ns"] - target > 100_000_000:
            raise ValueError("촬영 대상 시각의 차량 표본 누락")
    values = list(row["transform"].values()) + list(row["velocity_mps"].values())
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError("원본 위치/속도에 비유한 값")
    if not math.isclose(math.hypot(row["velocity_mps"]["x"], row["velocity_mps"]["y"]),
                        row["speed_mps"], abs_tol=1e-9):
        raise ValueError("원본 평면 속도 불일치")
    return row


def capture_plan():
    rows = []
    for name, run_id, selector, description in SELECTIONS:
        folder = CAMPAIGN / run_id
        meta = json.loads((folder / "metadata.json").read_text())
        result = json.loads((folder / "result.json").read_text())
        samples = [json.loads(line) for line in (folder / "vehicle_states.jsonl").read_text().splitlines()]
        sample = selected_sample(meta, result, samples, selector)
        rows.append({"image": name + ".png", "run_id": run_id, "selector": selector,
                     "description": description, "source_sample": sample,
                     "source_host_from_t0_s": (sample["host_monotonic_ns"] - meta["t0_ns"]) / 1e9,
                     "source_run_status": result["status"], "source_map": meta["map"]})
    return rows


def ports_open():
    found = []
    for port in (2000, 2001):
        with socket.socket() as sock:
            sock.settimeout(.3)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                found.append(port)
    return found


def group_members(pgid):
    """직접 시작한 프로세스군만 확인하고 다른 앱의 인자는 수집하지 않는다."""
    out = subprocess.check_output(["ps", "-eo", "pid=,pgid=,comm="], text=True)
    return [{"pid": int(parts[0]), "name": parts[2]} for line in out.splitlines()
            if len(parts := line.split(maxsplit=2)) == 3 and int(parts[1]) == pgid]


def shutdown_verdict(returncode, log_text, open_ports, members, escalated):
    """포트 해제만으로 정상 종료를 주장하지 않는다."""
    markers = [m for m in ("Signal 11", "Segmentation fault", "Fatal error", "SIGSEGV") if m in log_text]
    ok = returncode == 0 and not markers and not open_ports and not members and not escalated
    return {"status": "PASS" if ok else "NOT_NORMAL", "returncode": returncode,
            "shell_equivalent_code": 128 - returncode if returncode is not None and returncode < 0 else returncode,
            "fatal_markers": markers, "ports_open_after": open_ports,
            "owned_group_remaining": members, "fallback_signals": escalated}


def stop_owned_server(process, log_path):
    signals = []
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGINT)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            signals.append("SIGTERM")
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                signals.append("SIGKILL")
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
    time.sleep(1)
    return shutdown_verdict(process.returncode, log_path.read_text(errors="replace"),
                            ports_open(), group_members(process.pid), signals)


def transform(carla, row):
    return carla.Transform(carla.Location(x=row["x"], y=row["y"], z=row["z"]),
                           carla.Rotation(pitch=row["pitch"], yaw=row["yaw"], roll=row["roll"]))


def wait_ready(carla, process, report, timeout=120):
    """포트 개방 후 새 연결로 재시도하고 실제 API 오류를 보존한다."""
    deadline = time.monotonic() + timeout
    report["readiness_errors"] = []
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("촬영 서버 조기 종료")
        if 2000 not in ports_open():
            time.sleep(1)
            continue
        client = carla.Client("127.0.0.1", 2000)
        client.set_timeout(5.)
        try:
            version = client.get_server_version()
            return client, version
        except RuntimeError as exc:
            report["readiness_errors"].append(str(exc))
            time.sleep(1)
    raise RuntimeError("촬영 서버 준비 시간 초과: " + str(report["readiness_errors"][-1:]))


def render(carla, client, plan, output, report):
    world = client.get_world()
    relevant = lambda: [a for a in world.get_actors()
                        if a.type_id.startswith(("vehicle.", "walker.", "sensor.", "controller."))]
    if relevant() or world.get_settings().synchronous_mode:
        raise RuntimeError("빈 전용 서버가 아닙니다")
    if not world.get_map().name.endswith("/Town04"):
        world = client.load_world("Town04")
    original_settings, original_weather = world.get_settings(), world.get_weather()
    vehicle = camera = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode, settings.fixed_delta_seconds = True, .05
        settings.no_rendering_mode = False
        settings.substepping, settings.max_substeps, settings.max_substep_delta_time = True, 10, .01
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        library = world.get_blueprint_library()
        vehicle = world.spawn_actor(library.find("vehicle.tesla.model3"), transform(carla, plan[0]["source_sample"]["transform"]))
        vehicle.set_simulate_physics(False)
        blueprint = library.find("sensor.camera.rgb")
        attributes = {"image_size_x": "1600", "image_size_y": "900", "fov": "70",
                      "sensor_tick": "0.0", "enable_postprocess_effects": "true",
                      "motion_blur_intensity": "0.0"}
        for key, value in attributes.items():
            if not blueprint.has_attribute(key):
                raise RuntimeError("지원하지 않는 카메라 설정: " + key)
            blueprint.set_attribute(key, value)
        camera_pose = {"x": -7., "y": -4., "z": 3.7, "pitch": -19., "yaw": 30., "roll": 0.}
        camera = world.spawn_actor(blueprint, transform(carla, camera_pose), attach_to=vehicle,
                                   attachment_type=carla.AttachmentType.Rigid)
        images = queue.Queue(maxsize=8)

        def receive(image):
            try:
                images.put_nowait(image)
            except queue.Full:
                try:
                    images.get_nowait()
                except queue.Empty:
                    pass
                try:
                    images.put_nowait(image)
                except queue.Full:
                    pass

        camera.listen(receive)
        report.update(map=world.get_map().name, camera_attributes=attributes,
                      camera_relative_transform=camera_pose, physics_enabled=False,
                      vehicle_attributes=dict(vehicle.attributes))
        (output / "captures").mkdir()
        for row in plan:
            vehicle.set_transform(transform(carla, row["source_sample"]["transform"]))
            # 같은 위치에서 충분히 렌더링한 뒤 해당 구간의 실제 카메라 프레임만 고른다.
            frames = {}
            for _ in range(35):
                frame = world.tick(15.)
                frames[frame] = world.get_snapshot().timestamp.elapsed_seconds
            minimum = min(frames) + 10
            deadline = time.monotonic() + 20
            chosen = None
            while time.monotonic() < deadline:
                try:
                    item = images.get(timeout=.5)
                except queue.Empty:
                    if chosen is not None:
                        break
                    continue
                if item.frame in frames and item.frame >= minimum:
                    chosen = item
            if chosen is None:
                raise RuntimeError("새 배치 위치에 대응하는 카메라 프레임 누락")
            path = output / "captures" / row["image"]
            chosen.save_to_disk(str(path))
            if not path.exists() or path.stat().st_size < 1000:
                raise RuntimeError("카메라 이미지 저장 실패")
            row.update(capture_frame=chosen.frame, capture_simulation_time_s=chosen.timestamp,
                       capture_world_time_s=frames[chosen.frame], image_sha256=sha(path),
                       captured_vehicle_transform=str(vehicle.get_transform()))
            if abs(chosen.timestamp - frames[chosen.frame]) > 1e-6:
                raise RuntimeError("사진 프레임과 촬영 시뮬레이션 시각 불일치")
            print(json.dumps({"captured": row["image"], "source_run": row["run_id"],
                              "source_frame": row["source_sample"]["frame"]}, ensure_ascii=False), flush=True)
            report["captures"].append(row)
    finally:
        errors = []
        for actor in (camera, vehicle):
            if actor is not None:
                try:
                    if actor is camera:
                        actor.stop()
                    if not actor.destroy():
                        errors.append("actor 제거 응답 false")
                except Exception as exc:
                    errors.append(str(exc))
        try:
            world.set_weather(original_weather)
            world.apply_settings(original_settings)
            report["remaining_relevant_actors"] = [{"id": a.id, "type_id": a.type_id} for a in relevant()]
            if report["remaining_relevant_actors"] or world.get_settings().synchronous_mode:
                errors.append("자원/설정 복구 불일치")
        except Exception as exc:
            errors.append(str(exc))
        report["cleanup_errors"] = errors
        report["cleanup_status"] = "FAIL" if errors else "PASS"


def execute(output):
    output = output.resolve()
    if not output.is_relative_to(ROOT) or output.is_relative_to(ROOT / "runs"):
        raise ValueError("출력은 원래 실험 폴더 밖의 프로젝트 내부여야 합니다")
    if output.exists():
        raise FileExistsError("기존 출력 폴더는 재사용하지 않습니다: " + str(output))
    if ports_open():
        raise RuntimeError("기존 서버가 있습니다. 이 도구는 다른 서버를 종료하지 않습니다")
    audit = json.loads(AUDIT.read_text())
    before = audit_inputs(audit["input_file_sha256"])
    plan = capture_plan()
    output.mkdir(parents=True)
    report = {"scope": SCOPE, "started_utc": datetime.now(timezone.utc).isoformat(),
              "actual_can": False, "main_trials_executed": 0, "new_performance_trials": 0,
              "selection_rule": "각 조건 첫 반복 R01, 고정 호스트 시각 또는 원본 정지 유지 완료 프레임",
              "notice": "본시험 후 원본 위치 로그로 별도 구성한 사진. 새 주행/제동 측정이 아님. 속도/제어값은 원본 로그.",
              "analysis_manifest_sha256": sha(AUDIT), "source_sha256": sha(__file__),
              "original_inputs_before": before, "captures": [], "capture_status": "INCOMPLETE"}
    write_json(output / "plan.json", plan)
    process = None
    log_path = output / "server.log"
    try:
        import carla
        binary = ROOT / "third_party/CARLA_0.9.15/CarlaUE4/Binaries/Linux/CarlaUE4-Linux-Shipping"
        command = [str(binary), "CarlaUE4", "-RenderOffScreen", "-nosound", "-quality-level=Low", "-carla-rpc-port=2000"]
        environment = dict(os.environ, __NV_PRIME_RENDER_OFFLOAD="1", __VK_LAYER_NV_optimus="NVIDIA_only")
        report["server_command"] = command
        with log_path.open("x") as log:
            process = subprocess.Popen(command, cwd=binary.parents[3], env=environment,
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        report["owned_server_pid"] = process.pid
        client, version = wait_ready(carla, process, report)
        report.update(client_version=client.get_client_version(), server_version=version)
        if version != "0.9.15" or client.get_client_version() != version:
            raise RuntimeError("CARLA 버전 불일치")
        client.set_timeout(30.)
        render(carla, client, plan, output, report)
        report["capture_status"] = "PASS" if report["cleanup_status"] == "PASS" else "CLEANUP_ERROR"
    except (Exception, KeyboardInterrupt) as exc:
        report["error"] = type(exc).__name__ + ": " + str(exc)
    finally:
        if process is not None:
            try:
                report["server_shutdown"] = stop_owned_server(process, log_path)
            except Exception as exc:
                report["server_shutdown"] = {"status": "ERROR", "error": str(exc),
                                             "owned_server_pid": process.pid}
        try:
            report["original_inputs_after"] = audit_inputs(audit["input_file_sha256"])
        except Exception as exc:
            report["original_inputs_after"] = {"status": "FAIL", "error": str(exc)}
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(output / "result.json", report)
    print(json.dumps({"scope": SCOPE, "capture_status": report["capture_status"],
                      "images": len(report["captures"]), "server_shutdown": report.get("server_shutdown"),
                      "output_dir": str(output)}, ensure_ascii=False), flush=True)
    return 0 if (report["capture_status"] == "PASS"
                 and report["original_inputs_after"]["status"] == "PASS"
                 and report.get("server_shutdown", {}).get("status") == "PASS") else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--start-owned-server", action="store_true", required=True,
                        help="전용 서버 시작과 촬영 후 종료를 명시적으로 허용")
    args = parser.parse_args()

    def interrupted(signum, frame):
        raise KeyboardInterrupt("촬영 중단 신호")

    signal.signal(signal.SIGTERM, interrupted)
    return execute(args.output_dir)


if __name__ == "__main__":
    sys.exit(main())
