#!/bin/bash
# Build the wheels builder image
set -xeuo pipefail
source circleci-build-skip.sh
# shellcheck disable=SC1091
source .env
REPO=docker.io/ajslater/codex-builder-base
CODEX_BUILDER_BASE_VERSION=$(./docker-version-codex-builder-base.sh)
IMAGE="${REPO}:${CODEX_BUILDER_BASE_VERSION}"
if [ "${1:-}" == "-f" ]; then
    shift
else
    docker pull "${IMAGE}" || true
    if docker inspect "${IMAGE}" --format="codex builder base image up to date"; then
        exit 0
    fi
fi

if [[ -z ${CIRCLECI:-} && -z ${PLATFORMS:-} ]]; then
    # shellcheck disable=SC1091
    source .env.platforms
fi

export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
export PLATFORMS
CODEX_BASE_VERSION=$(./docker-version-codex-base.sh)
export CODEX_BASE_VERSION
export CODEX_BUILDER_BASE_VERSION
ARCH=$(uname -m)
HOST_CACHE_DIR="./cache/packages/$ARCH"
mkdir -p "$HOST_CACHE_DIR/pypoetry" "$HOST_CACHE_DIR/pip"
export HOST_CACHE_DIR
if [ -n "${PLATFORMS:-}" ]; then
    PLATFORM_ARG=(--set "*.platform=$PLATFORMS")
else
    PLATFORM_ARG=()
fi

# shellcheck disable=2068
docker buildx bake \
    ${PLATFORM_ARG[@]:-} \
    --set "*.tags=$REPO:${CODEX_BUILDER_BASE_VERSION}" \
    --push \
    codex-builder-base
