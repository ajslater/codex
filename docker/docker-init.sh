#!/bin/bash
set -euo pipefail
export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
# login to docker using environment variables
echo "$DOCKER_PASS" | docker login --username="$DOCKER_USER" --password-stdin
# shellcheck disable=SC1091
source .env.platforms
if [[ $PLATFORMS == linux/armhf ]]; then
    PLATFORMS=arm
elif [[ $(uname -m) == "x86_64" ]]; then
    PLATFORMS=
elif [[ $(uname -m) == "aarch64" ]]; then
    PLATFORMS=aarch64
fi
if [[ -n ${PLATFORMS:-} ]]; then
    docker run --rm --privileged tonistiigi/binfmt:latest --install "$PLATFORMS"
fi
# buildx requires creating a builder on a fresh system
docker buildx create --use
