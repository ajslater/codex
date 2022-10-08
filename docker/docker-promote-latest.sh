#!/bin/bash
# push a latest tag from an-arch repo version
set -euo pipefail
REPO=docker.io/ajslater/codex
ARCH_REPO=docker.io/ajslater/codex-arch
ARCHES=(x86_64 aarch64) # aarch32)

PKG_VERSION=$1
AMEND_TAGS=()
for arch in "${ARCHES[@]}"; do
    AMEND_TAGS+=("--amend" "$ARCH_REPO:${PKG_VERSION}-${arch}")
done

if [[ $PKG_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]$ ]]; then
    # If the version is just numbers push it as latest
    LATEST_TAG="$REPO:latest"
    echo "Creating $LATEST_TAG."
    CREATE_LATEST_ARGS=("$LATEST_TAG" "${AMEND_TAGS[@]}")
    docker manifest create "${CREATE_LATEST_ARGS[@]}"
    docker manifest push "$LATEST_TAG"
else
    echo "Not a valid latest version"
fi
