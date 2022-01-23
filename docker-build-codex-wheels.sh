#!/bin/bash
# get or build and push codex-wheels multiarch image
set -eux

# shellcheck disable=SC1091
source .env
CODEX_WHEELS_VERSION=$(./docker-version-codex-wheels.sh)
REPO=docker.io/ajslater/codex-wheels
IMAGE="${REPO}:${CODEX_WHEELS_VERSION}"
if [ "${1:-}" == "-f" ]; then
    shift
else
    docker pull "${IMAGE}" || true
    if docker inspect "${IMAGE}" --format="codex wheels image up to date"; then
        exit 0
    fi
fi

if [[ -z ${PLATFORMS:-} ]]; then
    # shellcheck disable=SC1091
    source .env.platforms
fi

if [ -n "${1:-}" ]; then
    CMD=$1
else
    # Different behavior for multiple vs single PLATFORMS
    # XXX --load behavior breaks build-codex.sh because it always
    #     tries to resolve wheels from docker.io
    # https://github.com/docker/cli/issues/3286
    # if [[ ${PLATFORMS:-} =~ "," ]]; then
    # more than one platform
    CMD="--push"
    #else
    #    # only one platform loading into docker works
    #    CMD="--load"
    #fi
fi

export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
CODEX_BUILDER_VERSION=$(./docker-version-codex-builder.sh)
export CODEX_BUILDER_VERSION
export CODEX_WHEELS_VERSION
export PLATFORMS
if [ -n "${PLATFORMS:-}" ]; then
    PLATFORM_ARG=(--set "*.platform=$PLATFORMS")
else
    PLATFORM_ARG=()
fi
if [[ ${PLATFORMS:-} =~ "," ]]; then
    LATEST_TAG=(--set "*.tags=$REPO:latest")
else
    LATEST_TAG=()
fi
# shellcheck disable=2068
docker buildx bake \
    ${PLATFORM_ARG[@]:-} \
    --set "*.tags=${IMAGE}" \
    ${LATEST_TAG[@]:-} \
    ${CMD:-} \
    codex-wheels
