#!/bin/bash
# Compute the version tag for ajslater/codex-base
set -euo pipefail
EXTRA_MD5S=("x x")

DEPS=(
    "$0"
    .dockerignore
    base.Dockerfile
    docker/docker-arch.sh
    docker/docker-build-image.sh
    docker/docker-env.sh
    docker/docker-env-filename.sh
    docker/docker-init.sh
    docker/docker-version-checksum.sh
    docker/docker-version-codex-arch.sh
    docker-compose.yaml
)

source ./docker/docker-version-checksum.sh
