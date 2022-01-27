#!/bin/bash
# Get the final runnable codex image version
set -euo pipefail
source .env
VERSION=${PKG_VERSION}
if [ "${CIRCLECI:-}" ]; then
    ARCH=$(./docker-arch.sh)
    VERSION=${VERSION}-${ARCH}
fi
echo "$VERSION"
