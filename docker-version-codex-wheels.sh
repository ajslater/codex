#!/bin/bash
# Get the final runnable codex image version
set -euo pipefail
source .env
CODEX_BUILDER_FINAL_VERSION=$(./docker-version-codex-builder-final.sh)
DEPS=(
    "$0"
    wheels.Dockerfile
    docker-build-codex-wheels.sh
)
DEPS_MD5S=$(md5sum "${DEPS[@]}")
VERSION=$(echo -e "$CODEX_BUILDER_FINAL_VERSION  codex-builder-final-version\n$DEPS_MD5S" |
    LC_ALL=C sort |
    md5sum |
    awk '{print $1}')
ARCH=$(./docker-arch.sh)
VERSION=${VERSION}-${ARCH}
echo "$VERSION"
