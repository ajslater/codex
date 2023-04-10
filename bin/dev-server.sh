#!/bin/bash
# Run the codex server
set -euxo pipefail
THIS_DIR="$(dirname "$0")/.."
cd "$THIS_DIR" || exit 1
export PYTHONPATH="${PYTHONPATH:-}:$THIS_DIR"
export DEBUG="${DEBUG:-1}"
export PYTHONDEVMODE="$DEBUG"
export PYTHONDONTWRITEBYTECODE=1
poetry run python3 ./codex/run.py
