#!/usr/bin/env bash
# Run all tests
set -euxo pipefail
mkdir -p test-results
LOGLEVEL=DEBUG uv run --group test pytest "$@"
# pytest-cov leaves .coverage.$HOST.$PID.$RAND files around while coverage itself doesn't
uv run --group test coverage erase || true
