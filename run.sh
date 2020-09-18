#!/bin/sh
# Run the codex server
cd "$(dirname "$0")" || exit 1
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
export PYTHONDONTWRITEBYTECODE=$DEV
poetry run python3 ./codex/run.py
