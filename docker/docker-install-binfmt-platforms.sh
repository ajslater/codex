#!/bin/bash
set -euxo pipefail
# shellcheck disable=SC1091
source .env
# shellcheck disable=SC1091
source .env.platforms
export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
docker run --rm --privileged tonistiigi/binfmt:latest --install "$PLATFORMS"
