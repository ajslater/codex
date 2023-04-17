#!/bin/bash
# Get the final runnable codex image version
set -euo pipefail
VERSION=$(./bin/version.sh)
if [ "${CIRCLECI-}" ]; then
    ARCH=$(./bin/docker/docker-arch.sh)
    VERSION=${VERSION}-${ARCH}
fi
echo "$VERSION"
