#!/usr/bin/env bash
# Save arch image
set -xeuo pipefail
. ./docker/machine-env.sh
ARCH=$(./docker/docker-arch.sh)
docker image save docker.io/ajslater/codex-arch:"$CODEX_ARCH_VERSION" --output codex-"$ARCH".tar
