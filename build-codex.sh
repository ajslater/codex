#!/bin/bash
# Build a codex docker image suitable for running from Dockerfile
set -euxo pipefail

# Load .env variables but with a mechanism to override PLATFORMS
source .env
if [ -z "${PLATFORMS:-}" ]; then
    source .env.platforms
fi

# Different behavior for multiple vs single PLATFORMS
if [ -n "${1:-}" ]; then
    CMD=$1
else
    if [[ ${PLATFORMS:-} =~ "," ]]; then
        # more than one platform
        CMD="--push"
    else
        # only one platform loading into docker works
        CMD="--load"
    fi
fi

WHEELS_VERSION=$(md5sum poetry.lock | awk '{print $1}')
CODEX_WHEEL=codex-${PKG_VERSION}-py3-none-any.whl
export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
export CODEX_WHEEL
export PLATFORMS
export RUNNABLE_BASE_VERSION
export WHEELS_VERSION
if [ -n "${PLATFORMS:-}" ]; then
    PLATFORM_ARG=(--set "*.platform=$PLATFORMS")
else
    PLATFORM_ARG=()
fi
# Build and cache
# shellcheck disable=2068
docker buildx bake codex \
    ${PLATFORM_ARG[@]:-} \
    --set "*.tags=$REPO:${PKG_VERSION}" \
    --set "*.tags=$REPO:latest" \
    ${CMD:-}
