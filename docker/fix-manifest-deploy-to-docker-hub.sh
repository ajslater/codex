#!/bin/bash
# Fix pushing final manifest for deploy because docker hub doesn't generate manifests now.
set -euxo pipefail

VERSION=$1

HUB_MULTI_TAG="ajslater/codex:${VERSION}"
HUB_ARM_TAG="${HUB_MULTI_TAG}-aarch64"
HUB_AMD_TAG="${HUB_MULTI_TAG}-x86_64"
LOCAL_MULTI_TAG=localhost/$HUB_MULTI_TAG
LOCAL_ARM_TAG=localhost/${HUB_ARM_TAG}
LOCAL_AMD_TAG=localhost/${HUB_AMD_TAG}

# pull arch images locally from docker hub
docker pull "$HUB_ARM_TAG"
docker pull --platform=amd64 "$HUB_AMD_TAG"

# tag both images for local registry
docker tag "$HUB_ARM_TAG" "$LOCAL_ARM_TAG"
docker tag "$HUB_AMD_TAG" "$LOCAL_AMD_TAG"

# run local registry
docker compose -f registry.yaml up -d

# push both images into local registry
docker push "$LOCAL_ARM_TAG"
docker push "$LOCAL_AMD_TAG"

#build local manifest
docker manifest create --insecure "$LOCAL_MULTI_TAG" -a "$LOCAL_ARM_TAG" -a "$LOCAL_AMD_TAG"

#push local manifest
docker manifest push --insecure "$LOCAL_MULTI_TAG"

#pull combined image
docker pull "$LOCAL_MULTI_TAG"

# Final push
docker buildx imagetools create -t "$HUB_MULTI_TAG" "$LOCAL_MULTI_TAG"

# promote pushed to latest
if [ "${2:-}" = "latest" ]; then
    ./docker-tag-remote-version-as-latest.sh "$VERSION"
fi

# remove old tags from repository
./docker-hub-remove-tags.sh "$HUB_ARM_TAG" "$HUB_AMD_TAG"
