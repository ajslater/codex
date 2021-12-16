#!/bin/bash
# get or build and push codex-wheels multiarch image
set -euo pipefail

WHEELS_VERSION=$(md5sum poetry.lock | awk '{print $1}')
IMAGE="ajslater/codex-wheels:${WHEELS_VERSION}"
if [ "${1:-}" != "-f" ]; then
    docker pull "${IMAGE}" || true
    if docker inspect "${IMAGE}" --format="codex wheels image up to date"; then
        exit 0
    fi
fi

REQ_FN=requirements.txt
poetry export --without-hashes --extras wheel --output "$REQ_FN"

source .env
if [[ -z $PLATFORMS ]]; then
    source .env.platforms
fi

# Different behavior for multiple vs single PLATFORMS
if [[ $PLATFORMS =~ "," ]]; then
    # more than one platform
    LOAD_OR_PUSH="--push"
else
    # only one platform loading into docker works
    LOAD_OR_PUSH="--load"
fi

export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
export WHEEL_BUILDER_VERSION=$WHEEL_BUILDER_VERSION
export WHEELS_VERSION
export PLATFORMS
docker buildx bake codex-wheels --set "*.platform=$PLATFORMS" \
    ${LOAD_OR_PUSH:-}
rm -f "$REQ_FN"
