#!/bin/bash
# initialize docker builder with correct emulators for this arch
set -euo pipefail

# login to docker using environment variables
echo "$DOCKER_PASS" | docker login --username="$DOCKER_USER" --password-stdin

# install emulator binaries if needed
EMULATORS=
if [[ ${PLATFORMS-} == "linux/armhf" ]]; then
  # this is the only arch i need to cross compile on circleci
  EMULATORS=arm
fi
if [[ -n ${EMULATORS-} ]]; then
  docker run --rm --privileged tonistiigi/binfmt:latest --install "$EMULATORS"
fi

# buildx requires creating a builder on a fresh system
BUILDER_NAME=codex-builder
if ! docker buildx ls | grep -q "$BUILDER_NAME"; then
  echo "Builder '${BUILDER_NAME}' does not exist. Creating it now..."
  docker buildx create --name "$BUILDER_NAME" --use
  echo "Builder '${BUILDER_NAME}' created and selected."
else
  echo "Builder '${BUILDER_NAME}' already exists. Selecting it now..."
  docker buildx use "$BUILDER_NAME"
fi

# optional
# docker buildx inspect --bootstrap
