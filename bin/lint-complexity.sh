#!/usr/bin/env bash
# Lint complexity
set -euo pipefail
if [ "$(uname)" != "Darwin" ]; then
  exit 0
fi

uv run --group lint complexipy
uv run --group lint radon mi --min B .
uv run --group lint radon cc --min C .
