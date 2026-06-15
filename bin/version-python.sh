#!/usr/bin/env bash
# Get version or set version for python.
set -euo pipefail
VERSION="${1:-}"
if [ "$VERSION" = "" ]; then
  uv version
else
  uv version "$VERSION"
fi
