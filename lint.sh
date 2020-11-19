#!/bin/bash
# Lint checks
set -euxo pipefail
poetry run flake8 .
poetry run isort --check-only --color .
poetry run black --check .
bash -c "cd frontend && eslint ."
prettier --check .
# hadolint Dockerfile*
shellcheck -x ./*.sh ./ci/*.sh
