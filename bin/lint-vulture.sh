#!/usr/bin/env bash
# Lint dead code with vulture
set -euo pipefail

# vulture fnmatches its excludes against absolute paths, so no pattern can skip
# the root's dot-dirs (.venv, .claude/worktrees/) without also skipping every
# file of a checkout under one. Pass the root's other entries instead of ".".
find . -mindepth 1 -maxdepth 1 ! -name '.*' \( -type d -o -type f -name '*.py' \) \
  -exec uv run --group lint vulture {} +
