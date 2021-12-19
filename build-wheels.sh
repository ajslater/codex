#!/bin/bash
# get or build and push codex-wheels multiarch image
set -eux

source .env
WHEELS_VERSION=$(./wheels-version.sh)
REPO=docker.io/ajslater/codex-wheels
IMAGE="${REPO}:${WHEELS_VERSION}"
if [ "${1:-}" != "-f" ]; then
    docker pull "${IMAGE}" || true
    if docker inspect "${IMAGE}" --format="codex wheels image up to date"; then
        exit 0
    fi
fi

if [[ -z ${PLATFORMS:-} ]]; then
    source .env.platforms
fi

if [ -n "${1:-}" ]; then
    CMD=$1
else
    # Different behavior for multiple vs single PLATFORMS
    if [[ ${PLATFORMS:-} =~ "," ]]; then
        # more than one platform
        CMD="--push"
    else
        # only one platform loading into docker works
        CMD="--load"
    fi
fi

export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
export WHEEL_BUILDER_VERSION=$WHEEL_BUILDER_VERSION
export WHEELS_VERSION
export PLATFORMS
if [ -n "${PLATFORMS:-}" ]; then
    PLATFORM_ARG=(--set "*.platform=$PLATFORMS")
else
    PLATFORM_ARG=()
fi
# shellcheck disable=2068
docker buildx bake \
    ${PLATFORM_ARG[@]:-} \
    --set "*.tags=${IMAGE}" \
    ${CMD:-} \
    codex-wheels
