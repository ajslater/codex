#!/bin/bash
# Create the docker .env for this architecture
set -euo pipefail
. ./docker/docker-env-filename.sh

if [[ $* == *base* ]]; then
  CODEX_VERSION=$(uv version --short)
  ARCH=$(./docker/docker-arch.sh)
  (
    echo "CODEX_BASE_VERSION=$(./docker/docker-version-codex-base.sh)"
    echo "CODEX_BUILDER_BASE_VERSION=$(./docker/docker-version-codex-builder-base.sh)"
    echo "CODEX_VERSION=${CODEX_VERSION}"
    echo "CODEX_ARCH_VERSION=${CODEX_VERSION}-${ARCH}"
    echo "CODEX_WHEEL=codex-${CODEX_VERSION}-py3-none-any.whl"
  ) > "$ENV_FN"
fi

if [[ $* == *dist-builder* ]]; then
  echo "CODEX_DIST_BUILDER_VERSION=$(./docker/docker-version-codex-dist-builder.sh)" >> "$ENV_FN"
fi
