#!/usr/bin/env bash
# Lint checks
set -euxo pipefail

####################
###### Python ######
####################
uv run --group lint ruff check .
uv run --group lint ruff format --check .
make typecheck
uv run --group lint skylos --no-upload --confidence 61 --category dead_code --no-provenance .
bin/lint-complexity.sh
uv run --group lint codespell .
