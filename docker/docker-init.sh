#!/bin/bash
set -euo pipefail
export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
# login to docker using environment variables
echo "$DOCKER_PASS" | docker login --username="$DOCKER_USER" --password-stdin
# I could detect only the platform we need, but this is fast.
# shellcheck disable=SC1091
source .env.platforms
docker run --rm --privileged tonistiigi/binfmt:latest --install "$PLATFORMS"
# buildx requires creating a builder on a fresh system
docker buildx create --use
