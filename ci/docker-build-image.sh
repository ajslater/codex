#!/usr/bin/env bash
# Generic image builder script
set -xeuo pipefail
. ./ci/machine-env.sh

# Set env
TARGET=$1 # the docker bake target to build
REPO=docker.io/ajslater/$1
VERSION_VAR=${TARGET^^}
VERSION_VAR=${VERSION_VAR//-/_}_VERSION
IMAGE="${REPO}:${!VERSION_VAR}"

if [ "${1-}" == "-f" ]; then
  shift
else
  # Skip build if image is already built. Optionally pull it.
  if docker manifest inspect "$IMAGE"; then
    echo "$IMAGE" is already built.
    if [[ $* == *pull* ]]; then
      docker image pull "$IMAGE"
    fi
    exit 0
  fi
fi

# Build
ARCH=$(./ci/machine-arch.sh)
export ARCH
docker buildx bake \
  --builder codex-builder \
  --file docker-bake.hcl \
  "$TARGET"

# Clean Repo
if [[ $* == *clean* ]]; then
  export UV_NO_DEV=1
  echo "$DOCKER_PASS" | uv run --only-group ci ./ci/cleanup-repo.py --no-confirm "$DOCKER_USER" ajslater "$TARGET" || true
fi
