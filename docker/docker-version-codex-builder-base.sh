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
    builder-base.Dockerfile
    builder-requirements.txt
)

source ./docker/docker-version-checksum.sh
