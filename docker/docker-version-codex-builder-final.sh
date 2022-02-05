#!/bin/bash
# Compute the version tag for codex-builder-final
set -euo pipefail

ENV_FN=$(./docker/docker-env-filename.sh)
# shellcheck disable=SC1090
source "$ENV_FN"
EXTRA_MD5S=(
    "$CODEX_BUILDER_BASE_VERSION  codex-builder-base-version"
    "$PKG_VERSION  codex-package-version")

# shellcheck disable=SC2046
DEPS=(
    "$0"
    builder-final.Dockerfile
)

source ./docker/docker-version-checksum.sh
