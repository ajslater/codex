#!/bin/bash
set -euo pipefail
source ./docker-env
TAG=v${PKG_VERSION}-$(echo "$CIRCLE_SHA1" | head -c 7)
docker tag "$IMAGE" "$IMAGE:$TAG"
docker tag "$IMAGE" "$IMAGE:latest"
docker login -u="$DOCKER_USER" -p="$DOCKER_PASS"
docker push "$REPO"
