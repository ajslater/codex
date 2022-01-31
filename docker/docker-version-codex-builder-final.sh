#!/bin/bash
# Compute the version tag for codex-builder-final
set -euo pipefail
CODEX_BUILDER_BASE_VERSION=$(./docker-version-codex-builder-base.sh)
# shellcheck disable=SC2046
DEPS=(
    "$0"
    builder-final.Dockerfile
    docker-build-codex-builder-final.sh
)
DEPS_MD5S=$(md5sum "${DEPS[@]}")
source .env
VERSION=$(echo -e "$CODEX_BUILDER_BASE_VERSION  codex-builder-base-version\n$PKG_VERSION  codex-package-version$DEPS_MD5S" |
    LC_ALL=C sort |
    md5sum |
    awk '{print $1}')
if [[ ${CIRCLECI:-} ]]; then
    ARCH=$(./docker-arch.sh)
    VERSION="${VERSION}-${ARCH}"
fi

echo "$VERSION"
