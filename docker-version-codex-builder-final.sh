#!/bin/bash
# Compute the version tag for codex-builder-final
set -euo pipefail
CODEX_BUILDER_BASE_VERSION=$(./docker-version-codex-builder-base.sh)
# shellcheck disable=SC2046
DEPS=(
    "$0"
    "dist/$CODEX_WHEEL"
    builder-final.Dockerfile
    docker-build-codex-builder-final.sh
)
DEPS_MD5S=$(md5sum "${DEPS[@]}")
VERSION=$(echo -e "$CODEX_BUILDER_BASE_VERSION  codex-builder-base-version\n$DEPS_MD5S" |
    LC_ALL=C sort |
    md5sum |
    awk '{print $1}')
if [[ ${CIRCLECI:-} ]]; then
    VERSION="${VERSION}-$(uname -m)"
fi
echo "$VERSION"
