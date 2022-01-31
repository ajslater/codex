#!/bin/bash
# Build a codex docker image suitable for running from Dockerfile
set -euxo pipefail

REPO=docker.io/ajslater/codex-arch
VERSION_VAR=CODEX_VERSION
SERVICE=codex
./docker/docker-build-image.sh $REPO $VERSION_VAR $SERVICE
