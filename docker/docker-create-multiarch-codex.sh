#!/bin/bash
# Combine arch specific images into a multiarch image
set -euxo pipefail
REPO=docker.io/ajslater/codex
# Don't use arch-repo anymore
#ARCH_REPO=docker.io/ajslater/codex-arch
ARCH_REPO=$REPO
ARCHES=(x86_64 aarch64) # aarch32)

pip3 install --upgrade pip
pip3 install --requirement builder-requirements.txt
PKG_VERSION=$(./version.sh)
VERSION_TAG=$REPO:$PKG_VERSION
echo "Creating $VERSION_TAG"
AMEND_TAGS=()
RM_TAGS=()
for arch in "${ARCHES[@]}"; do
    TAG="${PKG_VERSION}-${arch}"
    IMAGE="$ARCH_REPO:${TAG}"
    AMEND_TAGS+=("--amend" "$IMAGE")
    RM_TAGS+=("$TAG")
done

CREATE_VERSION_ARGS=("$VERSION_TAG" "${AMEND_TAGS[@]}")
docker manifest create "${CREATE_VERSION_ARGS[@]}"
docker manifest push "$VERSION_TAG"
echo "Created tag: ${VERSION_TAG}."

# cleanup main repo
./docker/docker-hub-remove-tags.sh "${RM_TAGS[@]}"
echo "Cleaned up intermediary arch tags."

if [[ $PKG_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]$ ]]; then
    # If the version is just numbers push it as latest
    docker/docker-tag-remote-version-as-latest.sh "$PKG_VERSION"
    echo "Created codex:${PKG_VERSION}"
fi
