#!/bin/bash
# Compute the version tag for ajslater/codex-base
set -euo pipefail
EXTRA_MD5S=("x x")

DEPS=(
    "$0"
    .dockerignore
    bin/docker/base.Dockerfile
    bin/docker/docker-arch.sh
    bin/docker/docker-build-image.sh
    bin/docker/docker-env.sh
    bin/docker/docker-env-filename.sh
    bin/docker/docker-init.sh
    bin/docker/docker-version-checksum.sh
    bin/docker/docker-version-codex-arch.sh
    docker-compose.yaml
)

source ./bin/docker/docker-version-checksum.sh
