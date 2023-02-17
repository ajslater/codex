#!/bin/bash
# Run the codex server
set -euxo pipefail
THIS_DIR="$(dirname "$0")"
cd "$THIS_DIR" || exit 1
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
export PYTHONPATH="${PYTHONPATH:-}:$THIS_DIR"
export DEBUG="${DEBUG:-1}"
export PYTHONDEVMODE="$DEBUG"
export PYTHONDONTWRITEBYTECODE=1 #"$DEBUG"
kill % || true
#./kill-codex.sh || true
poetry run python3 ./codex/run.py
