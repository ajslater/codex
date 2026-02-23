#!/usr/bin/env bash
# Lint checks
set -euxo pipefail

####################
###### Python ######
####################
uv run --group lint ruff check .
uv run --group lint ruff format --check .
uv run --group lint --group test basedpyright
uv run --group lint vulture .
bin/lint-complexity.sh
uv run --group lint codespell .
