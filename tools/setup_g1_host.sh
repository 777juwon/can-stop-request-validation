#!/usr/bin/env bash
set -euo pipefail

# Host-only prerequisites. This script does not run a transport experiment.
if [[ $# -ne 0 ]]; then
    echo "Usage: sudo bash tools/setup_g1_host.sh" >&2
    exit 2
fi
if [[ ${EUID} -ne 0 ]]; then
    echo "Run with sudo: sudo bash tools/setup_g1_host.sh" >&2
    exit 2
fi

/usr/bin/apt-get install --no-install-recommends -y can-utils vulkan-tools
/usr/sbin/modprobe vcan

if [[ ! -e /sys/class/net/vcan0 ]]; then
    /usr/sbin/ip link add dev vcan0 type vcan
fi

# Refuse a physical interface or any other device that happens to use this name.
/usr/sbin/ip -details -json link show dev vcan0 | /usr/bin/python3 -c '
import json
import sys
items = json.load(sys.stdin)
if len(items) != 1 or items[0].get("linkinfo", {}).get("info_kind") != "vcan":
    raise SystemExit("Refusing to change vcan0: device type is not vcan")
'
/usr/sbin/ip link set dev vcan0 up
/usr/bin/dpkg-query -W -f='${binary:Package}\t${Version}\n' can-utils vulkan-tools
/usr/sbin/ip -details link show dev vcan0
echo "Host prerequisites ready. G1 frame-exchange verification is a separate step."
