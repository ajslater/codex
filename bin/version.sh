#!/bin/bash
# Get version or set version in Frontend & API.
set -euo pipefail
VERSION="${1:-}"
TOML_PATH="--toml-path=pyproject.toml"
if [ "$VERSION" = "" ]; then
  uv run toml get "$TOML_PATH" project.version
else
  uv run toml set "$TOML_PATH" project.version "$VERSION"
  if [ -d frontend ]; then
    cd frontend
    npm version --allow-same-version "$VERSION"
  fi
fi
