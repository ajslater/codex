#!/bin/bash
# Push precached images to hub
set -xeuo pipefail
# shellcheck disable=SC1091
source .env

export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
export BUILDX_NO_DEFAULT_LOAD=1
docker buildx build \
    --platform "$PLATFORMS" \
    --build-arg "BUILDER_VERSION=$BUILDER_VERSION" \
    --build-arg "WHEEL_BUILDER_VERSION=$WHEEL_BUILDER_VERSION" \
    --build-arg "RUNNABLE_BASE_VERSION=$RUNNABLE_BASE_VERSION" \
    --build-arg "PKG_VERSION=$PKG_VERSION" \
    --tag "$REPO:${PKG_VERSION}" \
    --tag "$REPO:latest" \
    --cache-from=type=local,src=cache \
    --push \
    .
