#!/bin/bash
# Get the final runnable codex image version
set -euo pipefail
source .env
if [ "${CIRCLECI:-}" ]; then
    ARCH=$(./docker-arch.sh)
    VERSION=${PKG_VERSION}-${ARCH}
fi
echo "$VERSION"
