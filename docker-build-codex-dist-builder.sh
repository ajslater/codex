#!/bin/bash
# Build the wheels builder image
set -xeuo pipefail
source circleci-build-skip.sh
# shellcheck disable=SC1091
source .env

export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
CODEX_BUILDER_VERSION=$(./docker-version-codex-builder.sh)
CODEX_WHEELS_VERSION=$(./docker-version-codex-wheels.sh)
export CODEX_WHEELS_VERSION
export CODEX_BUILDER_VERSION

docker buildx bake --load codex-dist-builder
