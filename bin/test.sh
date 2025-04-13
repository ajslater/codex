#!/bin/bash
# Run all tests
set -euxo pipefail
mkdir -p test-results
LOGLEVEL=DEBUG uv run pytest "$@"
# pytest-cov leaves .coverage.$HOST.$PID.$RAND files around while coverage itself doesn't
uv run coverage erase || true
