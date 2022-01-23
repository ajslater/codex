#!/bin/bash
# Compute the version tag for ajslater/codex-builder
set -euo pipefail
CODEX_BUILDER_BASE_VERSION=$(./docker-version-codex-builder-base.sh)
# shellcheck disable=SC2046
read -ra SOURCE_DEPS <<<$(find codex frontend -type f \( ! -path "*node_modules*" ! -path "*codex/static_build*" ! -path "*codex/static_root*" ! -name "*~" ! -name "*.pyc" \))
DEPS=(
    "$0"
    .dockerignore
    builder.Dockerfile
    pyproject.toml
    poetry.lock
    "${SOURCE_DEPS[@]}"
)
DEPS_MD5S=$(md5sum "${DEPS[@]}")
echo -e "$CODEX_BUILDER_BASE_VERSION  codex-builder-base-version\n$DEPS_MD5S" |
    LC_ALL=C sort |
    md5sum |
    awk '{print $1}'
