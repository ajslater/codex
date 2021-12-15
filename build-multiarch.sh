#!/bin/bash
# Build a codex docker image suitable for running from Dockerfile
# Building it takes so long that login credentials time out.
# So cache it in the buildx buildcache and push it later.
set -xeuo pipefail

# Load .env variables but with a mechanism to override PLATFORMS
if [ -n "${PLATFORMS:-}" ]; then
    OVERRIDE_PLATFORMS=$PLATFORMS
fi
source .env
if [ -n "${OVERRIDE_PLATFORMS:-}" ]; then
    PLATFORMS=$OVERRIDE_PLATFORMS
fi

export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1

# Different behavior for multiple vs single PLATFORMS
if [[ $PLATFORMS =~ "," ]]; then
    # more than one platform
    export BUILDX_NO_DEFAULT_LOAD=1
else
    # only one platform loading into docker works
    LOAD="--load"
fi

# Build and cache
docker buildx build \
    --platform "$PLATFORMS" \
    --build-arg "BUILDER_VERSION=$BUILDER_VERSION" \
    --build-arg "WHEEL_BUILDER_VERSION=$WHEEL_BUILDER_VERSION" \
    --build-arg "RUNNABLE_BASE_VERSION=$RUNNABLE_BASE_VERSION" \
    --build-arg "PKG_VERSION=$PKG_VERSION" \
    --tag "$REPO:${PKG_VERSION}" \
    --tag "$REPO:latest" \
    --cache-to=type=local,dest=cache,mode=max \
    ${LOAD:-} \
    .
