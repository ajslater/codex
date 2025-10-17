#!/bin/bash
set -euxo pipefail
. ./docker/machine-env.sh
IMAGE=docker.io/ajslater/codex
ARCH_IMAGE="ajslater/codex-arch:${PKG_VERSION}"
if [[ $PKG_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  CODEX_LATEST=1
fi

#docker image pull --platform amd64 "ajslater/codex-arch:${PKG_VERSION}-amd64"
#docker image pull --platform arm64 "ajslater/codex-arch:${PKG_VERSION}-arm64"

docker image load -i codex-amd64.tar
docker image load -i codex-arm64.tar

TAG_ARGS=(-t "$IMAGE:$PKG_VERSION")
if [[ -v $CODEX_LATEST ]]; then
  # If the version is just numbers push it as latest
  TAG_ARGS+=(-t "$IMAGE":latest)
fi

docker buildx imagetools create \
  "${TAG_ARGS[@]}" \
  "${ARCH_IMAGE}-amd64" \
  "${ARCH_IMAGE}-arm64"

docker buildx imagetools inspect "$IMAGE:$PKG_VERSION"
if [[ -v $CODEX_LATEST ]]; then
  docker buildx imagetools inspect "$IMAGE:latest"
fi
