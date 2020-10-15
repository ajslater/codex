#!/bin/sh
# Run the codex server
THIS_DIR="$(dirname "$0")"
cd "$THIS_DIR" || exit 1
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
export PYTHONDONTWRITEBYTECODE=$DEV
export PYTHONPATH="$PYTHONPATH:$THIS_DIR"
poetry run python3 ./codex/run.py
