#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd -- "${project_dir}"
"${project_dir}/.venv/bin/python" -I -m unittest discover -s tests -t . -v
"${project_dir}/.venv/bin/python" -I -m pip --no-cache-dir --disable-pip-version-check check
bash -n tools/setup_g1_host.sh tools/start_carla_0915.sh tools/run_self_checks.sh
git diff --check
