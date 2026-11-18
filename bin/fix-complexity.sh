#!/usr/bin/env bash
# Fix complexity
# Rewrites only functions over the complexity limit; lint-complexity.sh fails on
# what it leaves. No --quiet: it would hide the diff of what --fix rewrote.
# ruff formats its rewrites.
set -euxo pipefail
uv run --group lint complexipy --fix --ignore-complexity
uv run --group lint ruff format .
