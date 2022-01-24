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

if [[ -z ${CIRCLECI:-} && -z ${PLATFORMS:-} ]]; then
    # shellcheck disable=SC1091
    source .env.platforms
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

# shellcheck disable=2068
docker buildx bake \
    ${PLATFORM_ARG[@]:-} \
    --set "*.tags=${IMAGE}" \
    --push \
    codex-wheels
