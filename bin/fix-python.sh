#!/usr/bin/env bash
# Fix common linting errors
set -euxo pipefail

# Python
# Rewrites only functions over the complexity limit; lint-complexity.sh fails on
# what it leaves. Before ruff, which formats its rewrites. --quiet would undo
# --ignore-complexity (complexipy 8.1.0).
uv run --group lint complexipy --fix --ignore-complexity
uv run --group lint ruff check --fix .
uv run --group lint ruff format .
