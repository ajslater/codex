#!/bin/bash
# Build the wheels builder image
set -xeuo pipefail
source .env
REPO=docker.io/ajslater/codex-base
CODEX_BASE_VERSION=$(./docker-version-codex-base.sh)
IMAGE="${REPO}:${CODEX_BASE_VERSION}"
if [ "${1:-}" == "-f" ]; then
    shift
else
    docker pull "${IMAGE}" || true
    if docker inspect "${IMAGE}" --format="codex base image up to date"; then
        exit 0
    fi
fi

if [[ -z ${PLATFORMS:-} ]]; then
    source .env.platforms
fi

export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
export PLATFORMS
export PYTHON_ALPINE_VERSION
export CODEX_BASE_VERSION
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
    --set "*.tags=$REPO:${CODEX_BASE_VERSION}" \
    ${LATEST_TAG[@]:-} \
    --push \
    codex-base
