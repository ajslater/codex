#!/bin/bash
# Build the wheels builder image
set -xeuo pipefail
./circleci/circleci-step-halt.sh

REPO=docker.io/ajslater/codex-dist-builder
VERSION_VAR=CODEX_DIST_BUILDER_VERSION
SERVICE=codex-dist-builder
./docker/docker-build-image.sh $REPO $VERSION_VAR $SERVICE

#source .env.versions
#docker-compose pull codex-dist-builder
