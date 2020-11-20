#!/bin/bash
# Build a codex docker image suitable for running from Dockerfile
set -xeuo pipefail
source .env

export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
docker buildx create --use
# shellcheck disable=SC2086
docker buildx build \
    --platform "$PLATFORMS" \
    --build-arg "BUILDER_VERSION=$BUILDER_VERSION" \
    --build-arg "WHEEL_BUILDER_VERSION=$WHEEL_BUILDER_VERSION" \
    --build-arg "RUNNABLE_BASE_VERSION=$RUNNABLE_BASE_VERSION" \
    --build-arg "PKG_VERSION=$PKG_VERSION" \
    --tag "$REPO:${PKG_VERSION}" \
    --tag "$REPO:latest" \
    ${PUSH:-} \
    .
