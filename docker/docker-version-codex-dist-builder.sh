#!/bin/bash
# Compute the version tag for ajslater/codex-dist-builder
set -euo pipefail

ENV_FN=$(./docker/docker-env-filename.sh)
# shellcheck disable=SC1090
source "$ENV_FN"
EXTRA_MD5S=("$CODEX_BUILDER_BASE_VERSION  codex-builder-base-version")

# shellcheck disable=SC2046
read -ra SOURCE_DEPS <<<"$(find codex frontend -type f \( \
    ! -path "*node_modules*" \
    ! -path "*codex/static_build*" \
    ! -path "*codex/static_root*" \
    ! -name "*~" \
    ! -name "*.pyc" \
    ! -name ".eslintcache" \
    ! -name ".DS_Store" \
    \))"
DEPS=(
    "$0"
    .dockerignore
    .eslintrc.cjs
    .prettierignore
    .remarkignore
    .shellcheckrc
    dist-builder.Dockerfile
    build-dist.sh
    collectstatic.sh
    lint.sh
    lint-backend.sh
    manage.py
    pm
    package.json
    package-lock.json
    pyproject.toml
    poetry.lock
    setup.cfg
    test-backend.sh
    "${SOURCE_DEPS[@]}"
)

source ./docker/docker-version-checksum.sh
