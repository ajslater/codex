#!/usr/bin/env bash
# Run all tests
set -euxo pipefail
mkdir -p test-results
# LOGLEVEL=DEBUG uv run --group test righttyper --all-files --overwrite --output-files --python-version 3.10 -m pytest "$@"
LOGLEVEL=DEBUG uv run --group test pytest "$@"
# pytest-cov leaves .coverage.$HOST.$PID.$RAND files around while coverage itself doesn't
uv run --group test coverage erase || true
