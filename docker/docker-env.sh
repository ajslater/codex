#!/bin/bash
# create the docker .env for this architecture
set -euo pipefail
ENV_FN=$(./docker/docker-env-filename.sh)

if [[ $* == *base* ]]; then
  echo "CODEX_BASE_VERSION=$(./docker/docker-version-codex-base.sh)" >"$ENV_FN"
fi

if [[ $* == *builder-base* ]]; then
  echo "CODEX_BUILDER_BASE_VERSION=$(./docker/docker-version-codex-builder-base.sh)" >>"$ENV_FN"
fi

if [[ $* == *dist-builder* ]]; then
  echo "CODEX_DIST_BUILDER_VERSION=$(./docker/docker-version-codex-dist-builder.sh)" >>"$ENV_FN"
fi

if [[ $* == *arch* ]]; then
  echo "CODEX_ARCH_VERSION=$(./docker/docker-version-codex-arch.sh)" >>"$ENV_FN"
fi

if [[ $* == *wheel* ]]; then
  PKG_VERSION=$(uv version --short)
  echo "CODEX_WHEEL=codex-${PKG_VERSION}-py3-none-any.whl" >>"$ENV_FN"
fi
