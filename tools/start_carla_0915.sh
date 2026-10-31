#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 1 || ${1:-2000} == *[!0-9]* ]]; then
    echo "Usage: bash tools/start_carla_0915.sh [rpc-port]" >&2
    exit 2
fi
rpc_port=${1:-2000}
if (( rpc_port < 1024 || rpc_port > 65534 )); then
    echo "RPC port must be 1024..65534; streaming uses the next port." >&2
    exit 2
fi
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
server_dir="${project_dir}/third_party/CARLA_0.9.15"
if [[ ! -f "${server_dir}/CarlaUE4.sh" ]]; then
    echo "CARLA 0.9.15 server is not extracted at ${server_dir}" >&2
    exit 1
fi
cd -- "${server_dir}"
# Per-process PRIME selection for the inspected AMD/NVIDIA laptop. NVIDIA's
# Vulkan layer puts the discrete GPU first; verify the actual server log too.
export __NV_PRIME_RENDER_OFFLOAD=1
export __VK_LAYER_NV_optimus=NVIDIA_only
exec bash ./CarlaUE4.sh -RenderOffScreen -nosound -quality-level=Low \
    "-carla-rpc-port=${rpc_port}"
