#!/bin/sh
# Run the codex server
THIS_DIR="$(dirname "$0")"
cd "$THIS_DIR" || exit 1
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
export PYTHONDONTWRITEBYTECODE="$DEBUG"
export PYTHONPATH="$PYTHONPATH:$THIS_DIR"
export LOGLEVEL="${LOGLEVEL:-VERBOSE}"
export PYTHONDEVMODE=1
export DEBUG=1
poetry run python3 ./codex/run.py
