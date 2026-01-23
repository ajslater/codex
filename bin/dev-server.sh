#!/bin/bash
# Run the codex server
set -euxo pipefail
THIS_DIR="$(dirname "$0")/.."
cd "$THIS_DIR" || exit 1
export DEBUG="${DEBUG:-1}"
export PYTHONDEBUG=1
export PYTHONDEVMODE="$DEBUG"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="${PYTHONPATH:-}:$THIS_DIR"
export PYTHONWARNINGS=always
#export CODEX_THROTTLE_OPDS=10
#export CODEX_THROTTLE_USER=10
#uv run python3 -X tracemalloc ./codex/run.py
uv run python3 ./codex/run.py
