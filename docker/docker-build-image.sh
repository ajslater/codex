#!/usr/bin/env bash
# Generic image builder script
set -xeuo pipefail
. ./docker/machine-env.sh

# Set env
TARGET=$1 # the docker bake target to build
REPO=docker.io/ajslater/$1
VERSION_VAR=${TARGET^^}
VERSION_VAR=${VERSION_VAR//-/_}_VERSION
IMAGE="${REPO}:${!VERSION_VAR}"

if [ "${1-}" == "-f" ]; then
  shift
else
  # Check if image is already built
  if docker manifest inspect "$IMAGE"; then
    echo "$IMAGE" is already built.
    if [[ $* == *pull* ]]; then
      docker image pull "$IMAGE"
    fi
    exit 0
  fi
fi

# Build
ARCH=$(./docker/docker-arch.sh)
export ARCH
docker buildx bake \
  --builder codex-builder \
  --file docker-bake.hcl \
  "$TARGET"

if [[ $* == *clean* ]]; then
  echo "$DOCKER_PASS" | uv run ./docker/cleanup-repo.py --password-stdin --no-confirm "$DOCKER_USER" ajslater "$TARGET"
fi
