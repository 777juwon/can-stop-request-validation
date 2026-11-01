#!/usr/bin/env bash
# 사용자가 단위 검사와 G1~G4의 단계별 실제 연결을 직접 실행한다.
# 실제 검사와 판정은 기존 도구가 수행하며 실행마다 새 증거 폴더를 사용한다.
set -euo pipefail

usage() {
    cat <<'USAGE'
사용법:
  bash tools/run_self_checks.sh check
  bash tools/run_self_checks.sh g1
  bash tools/run_self_checks.sh g3-can
  bash tools/run_self_checks.sh g2 --exclusive-server [--allow-world-load]
  bash tools/run_self_checks.sh g3 --exclusive-server [--allow-world-load]
  bash tools/run_self_checks.sh g4 --exclusive-server [--allow-world-load]
  bash tools/run_self_checks.sh preliminary

check: 단위 검사, Python 의존성, 셸 문법과 Git 공백 검사
g1: 이미 준비된 vcan0에서 독립 송신기와 수신기의 실제 프레임 교환
g2: 별도로 시작한 전용 CARLA 서버에서 실제 차속과 제동 확인
g3-can: CARLA 없이 StopRequest의 독립 송수신만 확인하는 G3 첫 단계
g3: 독립 CAN 요청의 수신부터 실제 CARLA 제동과 차속까지 확인
g4: A 방식의 거리 메시지 중단부터 실제 정지까지 T-03 한 번 확인
preliminary: CARLA 없이 vcan0에서 4개 시나리오 x A/B 예비시험 8개 실행

G2/G3/G4는 127.0.0.1:2000을 사용한다. 다른 시험이나 제어 프로그램을 먼저 종료한다.
--exclusive-server: 다른 tick/제어 프로그램이 없는 전용 서버임을 명시
--allow-world-load: 빈 서버의 맵을 Town04로 바꾸는 것을 허용
이 스크립트는 시스템 설치, 인터페이스 생성, 서버 시작을 자동 수행하지 않는다.
USAGE
}

mode=${1:-help}
if [[ $# -gt 0 ]]; then shift; fi
case "${mode}" in
    help|-h|--help) usage; exit 0 ;;
    check|g1|g3-can|preliminary)
        if [[ $# -ne 0 ]]; then usage >&2; exit 2; fi
        ;;
    g2|g3|g4)
        exclusive=0
        for option in "$@"; do
            case "${option}" in
                --exclusive-server) exclusive=1 ;;
                --allow-world-load) ;;
                *) usage >&2; exit 2 ;;
            esac
        done
        if [[ ${exclusive} -ne 1 ]]; then
            echo "G2/G3/G4는 --exclusive-server로 전용 서버 사용을 명시해야 합니다." >&2
            exit 2
        fi
        ;;
    *) usage >&2; exit 2 ;;
esac

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd -- "${project_dir}"
python_path="${project_dir}/.venv/bin/python"
if [[ ! -x "${python_path}" ]]; then
    echo "프로젝트 Python 환경이 없습니다. 설치 기록을 먼저 확인하세요." >&2
    exit 2
fi
if [[ ${mode} == check ]]; then
    exec bash tools/check_project.sh
fi

# 기존 결과를 덮어쓰지 않는다. 최종 폴더 생성과 중복 검사는 검사 도구가 맡는다.
run_id="$(date -u +%Y%m%dT%H%M%S%NZ)-$$"
output_dir="evidence/manual/${mode}-${run_id}"
echo "실행 증거 위치: ${project_dir}/${output_dir}"
case "${mode}" in
    g1)
        exec "${python_path}" -I tools/g1_vcan_smoke.py \
            --interface vcan0 --output-dir "${output_dir}"
        ;;
    g2)
        exec "${python_path}" -I tools/g2_carla_smoke.py \
            --host 127.0.0.1 --port 2000 --output-dir "${output_dir}" "$@"
        ;;
    g3-can)
        exec "${python_path}" -I tools/g3_request_smoke.py \
            --interface vcan0 --output-dir "${output_dir}"
        ;;
    g3)
        exec "${python_path}" -I tools/g3_carla_smoke.py \
            --interface vcan0 --host 127.0.0.1 --port 2000 --output-dir "${output_dir}" "$@"
        ;;
    g4)
        exec "${python_path}" -I tools/g4_carla_smoke.py \
            --interface vcan0 --host 127.0.0.1 --port 2000 --output-dir "${output_dir}" "$@"
        ;;
    preliminary)
        exec "${python_path}" -I tools/run_message_preliminary.py \
            --interface vcan0 --output-dir "${output_dir}"
        ;;
esac
