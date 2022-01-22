#!/bin/bash
# Compute the version tag for ajslater/codex-builder
set -euo pipefail
CODEX_BASE_VERSION=$(./docker-version-codex-base.sh)
IFS=" " read -r -a SHELLCHECK_DEPS <<<"$(find vendor/shellcheck -type f \( ! -name "*~" \))"
DEPS=(
    "$0"
    .dockerignore
    builder.Dockerfile
    builder-requirements.txt
    docker-build-codex-builder.sh
    "${SHELLCHECK_DEPS[@]}"
)
DEPS_MD5S=$(md5sum "${DEPS[@]}")
echo -e "$CODEX_BASE_VERSION  codex-base-version\n$DEPS_MD5S" \
    | LC_ALL=C sort \
    | md5sum \
    | awk '{print $1}'
