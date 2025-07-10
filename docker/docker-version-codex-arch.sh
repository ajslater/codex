#!/bin/bash
# Get the final runnable codex image version
set -euo pipefail
VERSION=$(uv version --short)
if [ "${CIRCLECI-}" ]; then
  ARCH=$(./docker/docker-arch.sh)
  VERSION=${VERSION}-${ARCH}
fi
echo "$VERSION"
