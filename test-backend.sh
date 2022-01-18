#!/bin/bash
# Run all codex tests
set -euxo pipefail
cd "$(dirname "$(readlink "$0")")"

./collectstatic.sh
poetry run pytest
# pytest-cov leaves .coverage.$HOST.$PID.$RAND files around while coverage itself doesn't
poetry run coverage erase || true
