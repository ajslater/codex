#!/bin/bash
# Build the wheels builder image
set -xeuo pipefail

REPO=docker.io/ajslater/codex-builder-base
VERSION_VAR=CODEX_BUILDER_BASE_VERSION
SERVICE=codex-builder-base
./docker/docker-build-image.sh $REPO $VERSION_VAR $SERVICE
