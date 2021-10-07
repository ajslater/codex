#!/bin/bash
# Lint checks
set -euxo pipefail
poetry run flake8 .
poetry run isort --check-only .
poetry run black --check .
bash -c "cd frontend && npx eslint --ext .js,.vue '**'"
prettier --check .
# hadolint Dockerfile*
shellcheck -x ./*.sh ./ci/*.sh
