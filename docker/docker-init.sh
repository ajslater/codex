#!/bin/bash
# initiallize docker builder with correct emulators for this arch
set -euo pipefail
./circleci/circleci-step-halt.sh
export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
# login to docker using environment variables
echo "$DOCKER_PASS" | docker login --username="$DOCKER_USER" --password-stdin
# install emulator binaries if i need to
EMULATORS=
if [[ ${PLATFORMS-} == "linux/armhf" ]]; then
    # this is the only arch i need to cross compile on circleci
    EMULATORS=arm
elif [[ "$(uname -m)" == "aarch64" ]]; then
    EMULATORS=aarch64
fi
if [[ -n ${EMULATORS-} ]]; then
    docker run --rm --privileged tonistiigi/binfmt:latest --install "$EMULATORS"
fi
# buildx requires creating a builder on a fresh system
docker buildx create --use
