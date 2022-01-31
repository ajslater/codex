#!/bin/bash
# Compute the version tag for ajslater/codex-builder-base
set -euo pipefail

source .env.versions
EXTRA_MD5S=("$CODEX_BASE_VERSION  codex-base-version")

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
    docker/docker-build-codex-builder-base.sh
    "${PYTHON_CACHER_DEPS[@]}"
)

source ./docker/docker-version-sum.sh
