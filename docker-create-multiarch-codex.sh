#!/bin/bash
# Combine arch specific images into a multiarch image
set -euo pipefail
source .env
REPO=docker.io/ajslater/codex
ARCH_REPO=docker.io/ajslater/codex-arch
ARCHES=(x86_64 aarch64) # aarch32)

VERSION_TAG=$REPO:$PKG_VERSION
echo "Creating $VERSION_TAG"
AMEND_TAGS=()
for arch in "${ARCHES[@]}"; do
    AMEND_TAGS+=("--amend $ARCH_REPO:${PKG_VERSION}-${arch}")
done

# shellcheck disable=2068
docker manifest create \
    ${VERSION_TAG} \
    ${AMEND_TAGS[@]}

# shellcheck disable=SC2068
docker manifest push $VERSION_TAG

if [[ $PKG_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]$ ]]; then
    # If the version is just numbers push it as latest
    LATEST_TAG="$REPO:latest"
    echo "Creating $LATEST_TAG."
    docker manifest create \
        $LATEST_TAG \
        --amend $VERSION_TAG

    docker manifest push $LATEST_TAG
fi
