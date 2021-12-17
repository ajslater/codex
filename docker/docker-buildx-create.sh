#!/bin/bash
# buildx requires creating a builder on a fresh system
set -euxo pipefail
export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
docker buildx create --use
