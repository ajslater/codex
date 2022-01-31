#!/bin/bash
# Compute the version tag for ajslater/codex-base
set -euo pipefail
# shellcheck disable=SC1091
DEPS=(
    "$0"
    .dockerignore
    base.Dockerfile
    docker/docker-build-codex-base.sh
)
DEPS_MD5S=$(md5sum "${DEPS[@]}")
source .env
echo -e "$PYTHON_ALPINE_VERSION  python-alpine-version\n$DEPS_MD5S" |
    docker-version-sum.sh
