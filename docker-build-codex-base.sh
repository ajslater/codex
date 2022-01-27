#!/bin/bash
# Build the wheels builder image
set -xeuo pipefail
# shellcheck disable=SC1091
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

if [[ -z ${CIRCLECI:-} && -z ${PLATFORMS:-} ]]; then
    # shellcheck disable=SC1091
    source .env.platforms
fi

export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
export PLATFORMS
export PYTHON_ALPINE_VERSION
export CODEX_BASE_VERSION
CODEX_DIST_BUILDER_VERSION=$(./docker-version-codex-dist-builder.sh)
export CODEX_DIST_BUILDER_VERSION
CODEX_BUILDER_FINAL_VERSION=$(./docker-version-codex-builder-final.sh)
export CODEX_BUILDER_FINAL_VERSION
if [ -n "${PLATFORMS:-}" ]; then
    PLATFORM_ARG=(--set "*.platform=$PLATFORMS")
else
    PLATFORM_ARG=()
fi

# shellcheck disable=2068
docker buildx bake \
    ${PLATFORM_ARG[@]:-} \
    --set "*.tags=$REPO:${CODEX_BASE_VERSION}" \
    --push \
    codex-base
