#!/usr/bin/env bash
# 패키지 설치 없이 이미 설치된 vcan 모듈로 가상 장치 하나만 준비한다.
set -euo pipefail

if [[ $# -ne 0 ]]; then
    echo "사용법: sudo bash tools/prepare_vcan0.sh" >&2
    exit 2
fi
if [[ ${EUID} -ne 0 ]]; then
    echo "관리자 권한이 필요합니다: sudo bash tools/prepare_vcan0.sh" >&2
    exit 2
fi

/usr/sbin/modprobe vcan
if [[ ! -e /sys/class/net/vcan0 ]]; then
    /usr/sbin/ip link add dev vcan0 type vcan
fi

# 같은 이름의 물리 장치가 있으면 UP 설정 전에 거부한다.
/usr/sbin/ip -details -json link show dev vcan0 | /usr/bin/python3 -c '
import json
import sys
items = json.load(sys.stdin)
if (len(items) != 1 or items[0].get("ifname") != "vcan0"
        or items[0].get("linkinfo", {}).get("info_kind") != "vcan"):
    raise SystemExit("vcan0가 가상 CAN 장치가 아니므로 변경하지 않습니다")
'
/usr/sbin/ip link set dev vcan0 up
/usr/sbin/ip -details link show dev vcan0
echo "vcan0 준비 완료. 실제 프레임 송수신 검사는 별도로 실행합니다."
