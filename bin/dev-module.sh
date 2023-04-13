#!/bin/bash
# Run a main method in an arbitrary module
set -euxo pipefail
THIS_DIR="$(dirname "$0")"
cd "$THIS_DIR" || exit 1
export PYTHONPATH="${PYTHONPATH:-}:$THIS_DIR"
export DEBUG="${DEBUG:-1}"
export PYTHONDEVMODE="$DEBUG"
export PYTHONDONTWRITEBYTECODE=1 #"$DEBUG"
poetry run python3 "$@"
