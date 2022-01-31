#!/bin/bash
# Compute the version tag for ajslater/codex-base
set -euo pipefail
# shellcheck disable=SC1091
source .env
EXTRA_MD5S=("$PYTHON_ALPINE_VERSION  python-alpine-version")

DEPS=(
    "$0"
    .dockerignore
    base.Dockerfile
    docker/build-image.sh
    docker/docker-env.sh
    docker/docker-version-checksum.sh
)

source ./docker/docker-version-checksum.sh
