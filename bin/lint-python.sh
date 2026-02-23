#!/usr/bin/env bash
# Lint checks
set -euxo pipefail

####################
###### Python ######
####################
uv run --group lint ruff check .
uv run --group lint ruff format --check .
make typecheck
uv run --group lint vulture .
bin/lint-complexity.sh
uv run --group lint codespell .
