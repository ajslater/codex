#!/bin/bash
# Load arch images and push all archs as one image to docker.io
set -euxo pipefail
. ./docker/machine-env.sh
IMAGE=docker.io/ajslater/codex
ARCH_IMAGE="ajslater/codex-arch"
ARCHES=(x86_64 aarch64)
if [[ $CODEX_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  # If the version is just numbers push it as latest
  CODEX_LATEST=1
fi

TAG_ARGS=(-t "$IMAGE:$CODEX_VERSION")
if [ "${CODEX_LATEST:-}" != "" ]; then
  TAG_ARGS+=(-t "$IMAGE":latest)
fi
IMAGE_ARGS=()
IMAGE_TAGS=()
for arch in "${ARCHES[@]}"; do
  # docker image load --input codex-"$arch".tar
  IMAGE_ARCH="$ARCH_IMAGE:$CODEX_VERSION-${arch}"
  IMAGE_ARGS+=("$IMAGE_ARCH")
  IMAGE_TAGS+=("${CODEX_VERSION}-${arch}")
done

docker buildx imagetools create \
  "${TAG_ARGS[@]}" \
  "${IMAGE_ARGS[@]}"

docker buildx imagetools inspect "$IMAGE:$CODEX_VERSION"
if [ "${CODEX_LATEST:-}" != "" ]; then
  docker buildx imagetools inspect "$IMAGE:latest"
fi

echo "$DOCKER_PASS" | uv run ./docker/cleanup-repo.py --password-stdin --keep 0 --no-confirm "$DOCKER_USER" ajslater codex-arch
