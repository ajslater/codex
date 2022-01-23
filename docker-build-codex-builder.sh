#!/bin/bash
# Build the wheels builder image
set -xeuo pipefail
source circleci-build-skip.sh
# shellcheck disable=SC1091
source .env
REPO=docker.io/ajslater/codex-builder
CODEX_BUILDER_VERSION=$(./docker-version-codex-builder.sh)
IMAGE="${REPO}:${CODEX_BUILDER_VERSION}"
if [ "${1:-}" == "-f" ]; then
    shift
else
    docker pull "${IMAGE}" || true
    if docker inspect "${IMAGE}" --format="codex builder image up to date"; then
        exit 0
    fi
fi

export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
CODEX_BUILDER_BASE_VERSION=$(./docker-version-codex-builder-base.sh)
export CODEX_BUILDER_BASE_VERSION
export CODEX_BUILDER_VERSION

if [[ -z ${PLATFORMS:-} ]]; then
    # shellcheck disable=SC1091
    source .env.platforms
fi
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
    --set "*.tags=$REPO:${CODEX_BUILDER_VERSION}" \
    ${LATEST_TAG[@]:-} \
    --push \
    codex-builder
