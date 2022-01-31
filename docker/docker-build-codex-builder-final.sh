#!/bin/bash
# Build a codex docker image suitable for running from Dockerfile
set -euxo pipefail

REPO=docker.io/ajslater/codex-builder-final
VERSION_VAR=CODEX_BUILDER_FINAL_VERSION
SERVICE=codex-builder-final
./docker/docker-build-image.sh $REPO $VERSION_VAR $SERVICE
