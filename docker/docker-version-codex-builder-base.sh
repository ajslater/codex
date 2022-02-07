#!/bin/bash
# Compute the version tag for ajslater/codex-builder-base
set -euo pipefail

ENV_FN=$(./docker/docker-env-filename.sh)
# shellcheck disable=SC1090
source "$ENV_FN"
EXTRA_MD5S=("$CODEX_BASE_VERSION  codex-base-version" "$WHEELS  wheels-dir")

# shellcheck disable=SC2046
read -ra HOST_CACHE_DIR_DEPS <<<$(find "$HOST_CACHE_DIR" -type f)
# shellcheck disable=SC2046
read -ra PYTHON_CACHER_DEPS <<<$(find python_cacher -type f \( \
    ! -path "*__pycache__*" \
    ! -name "*~" \
    \))
DEPS=(
    "$0"
    .dockerignore
    builder-base.Dockerfile
    builder-requirements.txt
    "${PYTHON_CACHER_DEPS[@]}"
    "${HOST_CACHE_DIR_DEPS[@]}"
)

source ./docker/docker-version-checksum.sh
