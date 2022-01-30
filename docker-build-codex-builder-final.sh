#!/bin/bash
# Build a codex docker image suitable for running from Dockerfile
set -euxo pipefail

# Load .env variables but with a mechanism to override PLATFORMS
# shellcheck disable=SC1091
source .env
if [[ -z ${CIRCLECI:-} && -z ${PLATFORMS:-} ]]; then
    # shellcheck disable=SC1091
    source .env.platforms
fi

# Different behavior for multiple vs single PLATFORMS
if [ -n "${1:-}" ]; then
    CMD=$1
else
    #    if [[ -z ${CIRCLECI:-} && ${PLATFORMS:-} =~ "," ]]; then
    # more than one platform
    CMD="--push"
    #    else
    # only one platform loading into docker works
#        CMD="--load"
#    fi
fi

export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
CODEX_BASE_VERSION=$(./docker-version-codex-base.sh)
export CODEX_BASE_VERSION
CODEX_BUILDER_BASE_VERSION=$(./docker-version-codex-builder-base.sh)
export CODEX_BUILDER_BASE_VERSION
CODEX_DIST_BUILDER_VERSION=$(./docker-version-codex-dist-builder.sh)
export CODEX_DIST_BUILDER_VERSION
CODEX_BUILDER_FINAL_VERSION=$(./docker-version-codex-builder-final.sh)
export CODEX_BUILDER_FINAL_VERSION
export CODEX_WHEEL=codex-${PKG_VERSION}-py3-none-any.whl
ARCH=$(./docker-arch.sh)
export HOST_CACHE_DIR="./cache/packages/$ARCH"
mkdir -p "$HOST_CACHE_DIR/pypoetry" "$HOST_CACHE_DIR/pip" "$HOST_CACHE_DIR/wheels"
if [ -n "${PLATFORMS:-}" ]; then
    PLATFORM_ARG=(--set "*.platform=$PLATFORMS")
else
    PLATFORM_ARG=()
fi
REPO=docker.io/ajslater/codex-builder-final

# Build and cache
# shellcheck disable=2068
docker buildx bake \
    ${PLATFORM_ARG[@]:-} \
    --set "*.tags=$REPO:$CODEX_BUILDER_FINAL_VERSION" \
    ${CMD:-} \
    codex-builder-final

docker-compose pull codex-builder-final
