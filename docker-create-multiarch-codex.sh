#!/bin/bash
# Combine arch specific images into a multiarch image
set -euo pipefail
source .env
REPO=docker.io/ajslater/codex
ARCH_REPO=docker.io/ajslater/codex-arch
ARCHES=(x86_64 aarch64) # aarch32)

OUTPUT_TAGS=("$REPO:$PKG_VERSION")
if [[ $PKG_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]$ ]]; then
    OUTPUT_TAGS+=("$REPO:latest")
fi

AMEND_TAGS=()
for arch in "${ARCHES[@]}"; do
    AMEND_TAGS+=("--amend $ARCH_REPO:${PKG_VERSION}-${arch}")
done

# shellcheck disable=2068
docker manifest create \
    ${OUTPUT_TAGS[@]} \
    ${AMEND_TAGS[@]}

# shellcheck disable=SC2068
docker manifest push ${OUTPUT_TAGS[@]}
