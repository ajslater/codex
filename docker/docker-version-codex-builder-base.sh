#!/bin/bash
# Compute the version tag for ajslater/codex-builder-base
set -euo pipefail
CODEX_BASE_VERSION=$(./docker/docker-version-codex-base.sh)
# shellcheck disable=SC2046
read -ra PYTHON_CACHER_DEPS <<<$(find python_cacher -type f \( \
    ! -path "*__pycache__*" \
    ! -name "*~" \
    \))
DEPS=(
    "$0"
    .dockerignore
    builder-base.Dockerfile
    builder-requirements.txt
    docker/docker-build-codex-builder-base.sh
    "${PYTHON_CACHER_DEPS[@]}"
)
DEPS_MD5S=$(md5sum "${DEPS[@]}")
echo -e "$CODEX_BASE_VERSION  codex-base-version\n$DEPS_MD5S" \
    | ./docker-version-sum.sh
