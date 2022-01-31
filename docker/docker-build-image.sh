#!/bin/bash
# Generic image builder script
set -xeuo pipefail
REPO=$1        # the image to build
VERSION_VAR=$2 # the version variable to use
SERVICE=$3     # the docker compose service to build

# shellcheck disable=SC1091
source .env
source .env.versions
IMAGE="${REPO}:${!VERSION_VAR}"
if [ "${1:-}" == "-f" ]; then
    shift
else
    docker pull "${IMAGE}" || true
    if docker inspect "${IMAGE}" --format="$IMAGE up to date"; then
        exit 0
    fi
fi

mkdir -p "$HOST_CACHE_DIR/pypoetry" "$HOST_CACHE_DIR/pip"

# Platform args
if [[ -z ${CIRCLECI:-} && -z ${PLATFORMS:-} ]]; then
    # shellcheck disable=SC1091
    source .env.platforms
fi
if [ -n "${PLATFORMS:-}" ]; then
    PLATFORM_ARG=(--set "*.platform=$PLATFORMS")
else
    PLATFORM_ARG=()
fi

export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
# shellcheck disable=2068
docker buildx bake \
    ${PLATFORM_ARG[@]:-} \
    --set "*.tags=${IMAGE}" \
    --push \
    "${SERVICE}"
