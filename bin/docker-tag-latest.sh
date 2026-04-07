#!/usr/bin/env bash
# Tag old version as latest
set -euo pipefail

if [[ "$#" -lt 3 ]]; then
  echo "Usage: $0 <registry> <image_name> <version_tag>"
  echo "Example: $0 ghcr.io ajslater/codex 1.10.3"
  exit 1
fi

# Configuration
REGISTRY=$1
IMAGE_NAME=$2
SOURCE_TAG=$3
TARGET_TAG="latest"

# Ensure DOCKER_PASS and DOCKER_USER are set in your environment
if [[ -z "$DOCKER_PASS" || -z "$DOCKER_USER" ]]; then
  echo "Error: DOCKER_PASS and DOCKER_USER environment variables must be set."
  exit 1
fi

# 1. Log in to registry
echo "Logging in to $REGISTRY..."
echo "$DOCKER_PASS" | docker login "$REGISTRY" -u "$DOCKER_USER" --password-stdin

# 2. Retag the multi-arch image
# This creates a new manifest on the registry side without downloading image layers
echo "Tagging $IMAGE_NAME:$SOURCE_TAG as $TARGET_TAG..."
docker buildx imagetools create \
  --tag "$REGISTRY/$IMAGE_NAME:$TARGET_TAG" \
  "$REGISTRY/$IMAGE_NAME:$SOURCE_TAG"

# shellcheck disable=SC2181
if [ $? -eq 0 ]; then
  echo "Successfully updated $TARGET_TAG"
else
  echo "Failed to update tag."
  exit 1
fi
