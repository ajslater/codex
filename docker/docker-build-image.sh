#!/usr/bin/env bash
# Generic image builder script
set -xeuo pipefail
REPO=docker.io/ajslater/$1
SERVICE=$1${2-} # the docker compose service to build
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
# It'd be nicer if i could bake --load and --push at the same time
# but that requires docker buildx bake to allow multiple outputs:
# https://github.com/moby/buildkit/issues/1555
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
