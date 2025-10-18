#!/bin/bash
set -euxo pipefail
. ./docker/machine-env.sh
IMAGE=docker.io/ajslater/codex
ARCH_IMAGE="docker.io/ajslater/codex-arch"
if [[ $PKG_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  CODEX_LATEST=1
fi

#docker image pull --platform x86_64 "ajslater/codex-arch:${PKG_VERSION}-x86_64"
#docker image pull --platform aarch64 "ajslater/codex-arch:${PKG_VERSION}-aarch64"

docker image load --input codex-x86_64.tar
docker image load --input codex-aarch64.tar

TAG_ARGS=(-t "$IMAGE:$PKG_VERSION")
if [ "${CODEX_LATEST:-}" != "" ]; then
  # If the version is just numbers push it as latest
  TAG_ARGS+=(-t "$IMAGE":latest)
fi

docker images # debug
docker buildx imagetools create \
  "${TAG_ARGS[@]}" \
  "${ARCH_IMAGE}:${PKG_VERSION}-x86_64" \
  "${ARCH_IMAGE}:${PKG_VERSION}-aarch64"

docker buildx imagetools inspect "$IMAGE:$PKG_VERSION"
if [ "${CODEX_LATEST:-}" != "" ]; then
  docker buildx imagetools inspect "$IMAGE:latest"
fi
