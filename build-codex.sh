#!/bin/bash
# Build a codex docker image suitable for running from Dockerfile
# Building it takes so long that login credentials time out.
# So cache it in the buildx buildcache and push it later.
set -xeuo pipefail

# Load .env variables but with a mechanism to override PLATFORMS
source .env
if [ -z "${PLATFORMS:-}" ]; then
    source .env.platforms
fi

export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1

# Different behavior for multiple vs single PLATFORMS
if [[ $PLATFORMS =~ "," ]]; then
    # more than one platform
    LOAD_OR_PUSH="--push"
else
    # only one platform loading into docker works
    LOAD_OR_PUSH="--load"
fi

WHEELS_VERSION=$(md5sum poetry.lock | awk '{print $1}')
CODEX_WHEEL=codex-${PKG_VERSION}-py3-none-any.whl
export CODEX_WHEEL
export PLATFORMS
export RUNNABLE_BASE_VERSION
export WHEELS_VERSION
# Build and cache
docker buildx bake codex \
    --set "codex.platform=$PLATFORMS" \
    ${LOAD_OR_PUSH:-}
unset PKG_VERSION
docker buildx bake codex \
    --set "*.platform=$PLATFORMS" \
    ${LOAD_OR_PUSH:-}
