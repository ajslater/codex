#!/usr/bin/env bash
# Get or set the node version: frontend/package.json if there is one, else ./package.json
set -euo pipefail
VERSION="${1:-}"
if [[ -d frontend ]]; then
  cd frontend
fi
if [[ ! -f package.json ]]; then
  echo "ERROR: no package.json in $PWD" >&2
  exit 1
fi
if [[ $VERSION == "" ]]; then
  bun pm pkg get name version
else
  # pkg set, unlike bun pm version, never commits or tags.
  bun pm pkg set "version=$VERSION"
fi
