#!/bin/bash
# Load arch images and push all archs as one image to docker.io
set -euxo pipefail
. ./docker/machine-env.sh
IMAGE=docker.io/ajslater/codex
ARCH_IMAGE="docker.io/ajslater/codex-arch"
if [[ $PKG_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  # If the version is just numbers push it as latest
  CODEX_LATEST=1
fi

docker image load --input codex-x86_64.tar
docker image load --input codex-aarch64.tar

TAG_ARGS=(-t "$IMAGE:$PKG_VERSION")
if [ "${CODEX_LATEST:-}" != "" ]; then
  TAG_ARGS+=(-t "$IMAGE":latest)
fi

# DEBUG ATTEMPT
docker images
docker images | awk 'NR > 1 {print $1}' | while read -r repository; do
  echo "$repository" | sed 's/./&_/g' | sed 's/_$//'
done

docker buildx imagetools create \
  "${TAG_ARGS[@]}" \
  "${ARCH_IMAGE}:${PKG_VERSION}-x86_64" \
  "${ARCH_IMAGE}:${PKG_VERSION}-aarch64"

docker buildx imagetools inspect "$IMAGE:$PKG_VERSION"
if [ "${CODEX_LATEST:-}" != "" ]; then
  docker buildx imagetools inspect "$IMAGE:latest"
fi
