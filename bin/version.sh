#!/bin/bash
# Get version or set version in Frontend & API.
set -euo pipefail
VERSION="${1:-}"
if [ "$VERSION" = "" ]; then
  poetry version | awk '{print $2};'
else
  poetry version "$VERSION"
  cd frontend
  npm version --allow-same-version "$VERSION"
fi
