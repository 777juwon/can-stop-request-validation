"""본시험 고정 설정, 80개 원래 ID와 소스 동결을 다룬다."""

import hashlib
import json
import math
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config/main_v1.json"
RUNS_PATH = ROOT / "config/main_runs_v1.json"
SOURCE_FILES = ("tools/main_plan.py", "tools/main_campaign.py", "tools/main_trial_oracle.py",
                "tools/g4_carla_smoke.py", "tools/g4_can_workers.py", "tools/g4_controller_core.py",
                "tools/sequence_controller_core.py", "tools/message_trial_oracle.py", "tools/g3_adapter_core.py",
                "tools/g3_carla_smoke.py", "tools/g3_integration_can.py", "tools/g3_request_smoke.py",
                "tools/g4_oracle.py", "tools/g2_carla_smoke.py", "tools/g3_integration_oracle.py",
                "requirements.lock.txt", "tools/start_carla_0915.sh", "config/stop_request_v1.dbc",
                "config/main_v1.json", "config/main_runs_v1.json")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def physics_digest(value):
    """절대좌표인 wheel position을 제외하고 물리 설정 문자열을 대조한다."""
    normalized = re.sub(r"position=Vector3D\([^)]*\)", "position=IGNORED_WORLD_COORDINATES", value)
    return digest(normalized.encode())


def load_config():
    config = json.loads(CONFIG_PATH.read_text())
    validate_config(config)
    return config


def validate_config(config):
    """고정 기준선 값의 사후 완화와 임의 운영 설정 혼입을 거부한다."""
    if not isinstance(config, dict):
        raise ValueError("고정 설정 JSON 객체가 필요합니다")
    exact = {"schema_version": 1, "baseline": "v1.0", "carla_version": "0.9.15", "map": "Town04",
             "vehicle_blueprint": "vehicle.tesla.model3", "weather": "ClearNoon", "spawn_index": 143,
             "sticky_control": True, "input_period_ms": 50, "poll_period_ms": 10, "timeout_ms": 200,
             "near_distance_cm": 200, "target_speed_kmh": 5, "initial_speed_tolerance_kmh": .5,
             "initial_speed_hold_s": 1, "fixed_delta_seconds": .05, "stop_speed_mps": .1,
             "stop_hold_s": .5, "stop_window_s": 2, "input_duration_s": 20, "trial_slots": 400,
             "repetitions": 10, "preparation_limit_s": 30, "corridor_distance_m": 100,
             "host": "127.0.0.1", "port": 2000, "rpc_timeout_s": 10}
    if any(type(config.get(key)) is not type(value) or config.get(key) != value for key, value in exact.items()):
        raise ValueError("본시험 고정 기준선/운영 설정이 일치하지 않습니다")
    if config != json.loads(CONFIG_PATH.read_text()):
        raise ValueError("현재 저장소의 고정 설정과 다른 실행 설정입니다")
    transform = config.get("spawn_transform", {})
    if set(transform) != {"x", "y", "z", "pitch", "yaw", "roll"} or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in transform.values()):
        raise ValueError("고정 spawn 좌표가 필요합니다")
    if not re.fullmatch("[0-9a-f]{64}", config.get("physics_normalized_sha256", "")):
        raise ValueError("사전 관측한 물리 설정 SHA가 필요합니다")


def expected_rows():
    rows = []
    for scenario in ("T-01", "T-02", "T-03", "T-04"):
        for repeat in range(1, 11):
            pair = f"M-{scenario}-R{repeat:02}"
            for variant in (("A", "B") if repeat % 2 else ("B", "A")):
                rows.append({"run_id": pair + "-" + variant,
                             "paired_run_id": pair + ("-B" if variant == "A" else "-A"),
                             "pair_id": pair, "scenario": scenario, "variant": variant,
                             "repeat": repeat, "order": len(rows) + 1})
    return rows


def load_rows():
    value = json.loads(RUNS_PATH.read_text())
    if value != {"baseline": "v1.0", "original_run_count": 80, "runs": expected_rows()}:
        raise ValueError("80개 원래 ID 또는 A/B 반복 순서가 일치하지 않습니다")
    return value["runs"]


def fixture_digest(scenario):
    """token을 0으로 정규화한 시나리오 바이트의 해시다. 판정 oracle가 아니다."""
    from tools.g4_can_workers import fixture_frames
    stream = [frame.hex() for n in range(400) for frame in fixture_frames(0, 256 + n, n, scenario)]
    return digest(canonical(stream))


def source_hashes():
    return {name: digest((ROOT / name).read_bytes()) for name in SOURCE_FILES}


def verify_run_rows(rows):
    if [{key: row[key] for key in expected_rows()[0]} for row in rows] != load_rows():
        raise ValueError("동결한 ID 목록 불일치")
    tokens = [row["run_token"] for row in rows]
    if len(set(tokens)) != 80 or any(type(t) is not int or not 0 <= t <= 0xFFFFFFFF for t in tokens):
        raise ValueError("80개 실행 token 식별 오류")


def verify_frozen(manifest):
    if manifest["source_sha256"] != source_hashes():
        raise ValueError("동결한 코드/설정이 바뀌었습니다. 기존 ID에 변경된 구현을 섞어 재개하지 않습니다")
    validate_config(manifest["config"])
    if manifest["config_sha256"] != digest(canonical(manifest["config"])):
        raise ValueError("고정 설정 해시 불일치")
    verify_run_rows(manifest["runs"])
    if manifest["fixture_sha256"] != {scenario: fixture_digest(scenario) for scenario in ("T-01", "T-02", "T-03", "T-04")}:
        raise ValueError("고정 입력 해시 불일치")


def project_output(path):
    result = Path(path).resolve()
    if not result.is_relative_to(ROOT) or result == ROOT:
        raise ValueError("출력은 이 프로젝트 안의 별도 폴더여야 합니다")
    return result
