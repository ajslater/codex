#!/bin/bash
# Build json choices for frontend using special script.
set -euo pipefail
THIS_DIR="$(dirname "$0")/.."
cd "$THIS_DIR" || exit 1
export PYTHONPATH="${PYTHONPATH:-}:$THIS_DIR"
CHOICES_DIR=frontend/src/choices
rm -rf "${CHOICES_DIR:?}"/*
poetry run codex/choices_to_json.py "$CHOICES_DIR"
