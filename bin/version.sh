#!/bin/bash
# Get version or set version in Frontend & API.
set -euo pipefail
VERSION="${1:-}"
if [ "$VERSION" = "" ]; then
  uv version
  if [ -d frontend ]; then
    cd frontend
    node -e "const {name, version} =  require('./package.json'); console.log(name, version);"
  fi
else
  uv version "$VERSION"
  if [ -d frontend ]; then
    cd frontend
    npm version --allow-same-version "$VERSION"
  fi
fi
