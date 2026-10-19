#!/usr/bin/env bash
# Fix common linting errors
set -euxo pipefail

# Python
bin/fix-complexity.sh
uv run --group lint ruff check --fix .
uv run --group lint ruff format .
