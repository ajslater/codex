#!/usr/bin/env bash
# Fix complexity
# Rewrites only functions over the complexity limit; lint-complexity.sh fails on
# what it leaves. --quiet would undo --ignore-complexity (complexipy 8.1.0).
# ruff formats its rewrites.
set -euxo pipefail
uv run --group lint complexipy --fix --ignore-complexity
uv run --group lint ruff format .
