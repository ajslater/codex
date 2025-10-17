#!/bin/bash
# Compute the version tag for ajslater/codex-builder-base
set -euo pipefail

ENV_FN=$(./docker/docker-env-filename.sh)
# shellcheck disable=SC1090
source "$ENV_FN"
EXTRA_MD5S=("$CODEX_BASE_VERSION  codex-base-version")
DEPS=(
  "$0"
  .dockerignore
  docker/builder-base.Dockerfile
  docker/debian.sources
  docker/docker-arch.sh
  docker/docker-build-image.sh
  docker/docker-env.sh
  docker/docker-env-filename.sh
  docker/docker-version-checksum.sh
  docker-compose.yaml
)

source ./docker/docker-version-checksum.sh
