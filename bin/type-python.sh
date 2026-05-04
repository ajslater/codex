#!/usr/bin/env bash
# Run all tests with righttyper
set -euxo pipefail
mkdir -p test-results
uv run --python 3.13 --group test --extra pdf \
  -m righttyper --include-files "$1/*" --overwrite --output-files --python-version 3.10 \
  -m pytest
# pytest-cov leaves .coverage.$HOST.$PID.$RAND files around while coverage itself doesn't
uv run --group test coverage erase || true
