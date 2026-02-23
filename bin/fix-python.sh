#!/usr/bin/env bash
# Fix common linting errors
set -euxo pipefail

# Python
uv run --group lint ruff check --fix .
uv run --group lint ruff format .
