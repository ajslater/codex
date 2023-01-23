#!/usr/bin/env bash
# Generic image builder script
set -xeuo pipefail
SERVICE=$1 # the docker compose service to build
REPO=docker.io/ajslater/${SERVICE}
VERSION_VAR=${SERVICE^^}
VERSION_VAR=${VERSION_VAR//-/_}_VERSION

ENV_FN=$(./docker/docker-env-filename.sh)
# shellcheck disable=SC1090
source "$ENV_FN"
IMAGE="${REPO}:${!VERSION_VAR}"
if [ "${1-}" == "-f" ]; then
    shift
else
    docker pull "$IMAGE" || true
    if docker inspect "$IMAGE" --format="$IMAGE up to date"; then
        exit 0
    fi
fi

# Platform args
if [[ -z ${CIRCLECI-} && -z ${PLATFORMS-} ]]; then
    # shellcheck disable=SC1091
    source .env.platforms
fi
if [ "${PLATFORMS-}" != "" ]; then
    PLATFORM_ARG=(--set "*.platform=$PLATFORMS")
else
    PLATFORM_ARG=()
fi

export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
export CODEX_BASE_VERSION
export CODEX_BUILDER_BASE_VERSION
export CODEX_DIST_BUILDER_VERSION
export CODEX_WHEEL
export PKG_VERSION
# shellcheck disable=2068
BAKE_ARGS=("${PLATFORM_ARG[@]}" --set "*.tags=${IMAGE}")
docker buildx bake \
    "${BAKE_ARGS[@]-}" \
    --load \
    "$SERVICE"
# Keep the above if it caches
# shellcheck disable=2068
docker buildx bake \
    "${BAKE_ARGS[@]-}" \
    --push \
    "$SERVICE"
# It'd be faster if i could bake --load and then bake push instead
# Try it
# docker pull "$IMAGE"
