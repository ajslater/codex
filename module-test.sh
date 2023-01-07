#!/bin/bash
# Run memory_profiler on a module
set -euxo pipefail
THIS_DIR="$(dirname "$0")"
cd "$THIS_DIR" || exit 1
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
export PYTHONPATH="${PYTHONPATH:-}:$THIS_DIR"
export DEBUG="${DEBUG:-1}"
export PYTHONDEVMODE="$DEBUG"
export PYTHONDONTWRITEBYTECODE=1 #"$DEBUG"
export LOGLEVEL="${LOGLEVEL:-VERBOSE}"
poetry run python3 -m memory_profiler ./module_test.py "$@"
