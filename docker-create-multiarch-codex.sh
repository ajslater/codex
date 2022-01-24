#!/bin/bash
# Combine arch specific images into a multiarch image
set -euo pipefail
IMAGE=codex
REPO=docker.io/ajslater/$IMAGE
source .env
docker manifest create \
    $REPO:$PKG_VERSION \
    --amend $IMAGE-x86_64:${PKG_VERSION} \
    --amend $IMAGE-aarch64:${PKG_VERSION}

docker manifest push $REPO:$PKG_VERSION
