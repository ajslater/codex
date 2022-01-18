#!/bin/bash
# Run all codex tests
set -euxo pipefail
# XXX without DEBUG pytest can't find choices.json because it hasn't been collected or built.
DEBUG=1 poetry run pytest
# pytest-cov leaves .coverage.$HOST.$PID.$RAND files around while coverage itself doesn't
poetry run coverage erase || true
bash -c "cd frontend && npm run test:unit"
