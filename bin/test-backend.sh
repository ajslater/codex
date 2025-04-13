#!/bin/bash
# Run all codex tests
set -euxo pipefail

export PYTHONPATH=.
BUILD=1 uv run pytest
# pytest-cov leaves .coverage.$HOST.$PID.$RAND files around while coverage itself doesn't
uv run coverage erase || true
