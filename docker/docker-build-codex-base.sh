#!/bin/bash
# Build the wheels builder image
set -xeuo pipefail

REPO=docker.io/ajslater/codex-base
VERSION_VAR=CODEX_BASE_VERSION
SERVICE=codex-base
./docker/docker-build-image.sh $REPO $VERSION_VAR $SERVICE
