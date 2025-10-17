#!/usr/bin/env bash
# Generic image builder script
set -xeuo pipefail

# Assert correct platform
#if [ "$1" == "amd64" ]; then
#  MACHINE=$(uname -m)
#  shift
#  if [ "$MACHINE" != "x86_64" ]; then
#    echo Skipping wrong platform: "$MACHINE" - "$1"
#    exit 0
#  fi
#fi

# Set env
REPO=docker.io/ajslater/$1
VERSION_VAR=${TARGET^^}
VERSION_VAR=${VERSION_VAR//-/_}_VERSION
#ENV_FN=$(./docker/docker-env-filename.sh)
# shellcheck disable=SC1090
#source "$ENV_FN"
IMAGE="${REPO}:${!VERSION_VAR}"

if [ "${1-}" == "-f" ]; then
  shift
else
  # Check if image is already built
  if docker manifest inspect "$IMAGE"; then
    echo "$IMAGE" is already built.
    if [ "$2" == "pull" ]; then
      docker image pull "$IMAGE"
    fi
    exit 0
  fi
fi

# Build
#export ARCH=$1
TARGET=$1 # the docker bake target to build
export CODEX_BASE_VERSION
export CODEX_BUILDER_BASE_VERSION
export CODEX_DIST_BUILDER_VERSION
export CODEX_WHEEL
export PKG_VERSION
docker buildx bake \
  --builder codex-builder \
  --file docker-bake.hcl \
  "$TARGET"
