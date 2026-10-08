#!/usr/bin/env bash
# Run all tests
set -euxo pipefail
mkdir -p test-results
status=0
LOGLEVEL=DEBUG uv run --group test pytest "$@" || status=$?
# pytest-cov leaves .coverage.$HOST.$PID.$RAND files around while coverage
# itself doesn't, so erase them whether or not the tests passed.
uv run --group test coverage erase || true
exit "$status"
