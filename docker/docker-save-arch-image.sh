#!/usr/bin/env bash
# Save arch image
set -xeuo pipefail
ARCH=$(./docker/docker-arch.sh)
docker image save docker.io/ajslater/codex-arch:"$CODEX_ARCH_VERSION" -o codex-"$ARCH".tar
