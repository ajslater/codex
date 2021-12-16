#!/bin/bash
# Build pip installable wheel and sdist files from Dockerfile.build
set -euxo pipefail
source .env

export COMPOSE_DOCKER_CLI_BUILD=1
export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
export BUILDER_VERSION=$BUILDER_VERSION
docker buildx bake codex-build \
    --load
