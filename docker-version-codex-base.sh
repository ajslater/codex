#!/bin/bash
# Compute the version tag for ajslater/codex-base
set -euo pipefail
source .env
DEPS=(
    "$0"
    .dockerignore
    base.Dockerfile
    docker-build-codex-base.sh
)
DEPS_MD5S=$(md5sum "${DEPS[@]}")
echo -e "$PYTHON_ALPINE_VERSION  python-alpine-version\n$DEPS_MD5S" |
    LC_ALL=C sort |
    md5sum |
    awk '{print $1}'
