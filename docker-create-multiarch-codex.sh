#!/bin/bash
# Combine arch specific images into a multiarch image
set -euo pipefail
IMAGE=codex
REPO=docker.io/ajslater/$IMAGE
if [[ $PKG_VERSION =~ [a-z] ]]; then
    LATEST_TAG=()
else
    LATEST_TAG=("$REPO:latest")
fi
source .env
# shellcheck disable=2068
docker manifest create \
    "$REPO:$PKG_VERSION" \
    ${LATEST_TAG[@]:-} \
    --amend $IMAGE-x86_64:${PKG_VERSION} \
    --amend $IMAGE-aarch64:${PKG_VERSION}

docker manifest push $REPO:$PKG_VERSION
