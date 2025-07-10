#!/bin/bash
# run a production-like server
export PYTHONPATH="$PYTHONPATH:$THIS_DIR"
uv run python3 ./codex/run.py
