#!/bin/bash
# Tag a remote version as latest
set -euo pipefail
export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
REPO=docker.io/ajslater/codex
VERSION=$1

docker buildx imagetools create "$REPO:$VERSION" --tag "$REPO:latest"
