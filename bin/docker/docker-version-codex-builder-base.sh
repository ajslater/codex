#!/bin/bash
# Compute the version tag for ajslater/codex-builder-base
set -euo pipefail

ENV_FN=$(./bin/docker/docker-env-filename.sh)
# shellcheck disable=SC1090
source "$ENV_FN"
EXTRA_MD5S=("$CODEX_BASE_VERSION  codex-base-version")
DEPS=(
    "$0"
    .dockerignore
    bin/docker/builder-base.Dockerfile
    builder-requirements.txt
)

source ./bin/docker/docker-version-checksum.sh
