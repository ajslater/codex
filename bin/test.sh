#!/bin/bash
# Run all tests
set -euxo pipefail
mkdir -p test-results
LOGLEVEL=DEBUG uv run pytest "$@"
# pytest-cov leaves .coverage.$HOST.$PID.$RAND files around while coverage itself doesn't
export UV_NO_DEV=1
uv run --group test coverage erase || true
