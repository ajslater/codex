#!/bin/bash
# Tag a remote version as latest
set -euo pipefail
REPO=docker.io/ajslater/codex
VERSION=$1

docker buildx imagetools create "$REPO:$VERSION" --tag "$REPO:latest"
