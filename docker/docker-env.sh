#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .env.build
rm -f .env
# shellcheck disable=SC1091,SC2129
cat <<EOF >>.env
PYTHON_ALPINE_VERSION=$PYTHON_ALPINE_VERSION
PKG_VERSION=${PKG_VERSION}
HOST_CACHE_DIR="./cache/packages/$(./docker/docker-arch.sh)"
CODEX_BASE_VERSION=$(./docker/docker-version-codex-base.sh)
EOF
echo "CODEX_BUILDER_BASE_VERSION=$(./docker/docker-version-codex-builder-base.sh)" >>.env
echo "CODEX_DIST_BUILDER_VERSION=$(./docker/docker-version-codex-dist-builder.sh)" >>.env
echo "CODEX_BUILDER_FINAL_VERSION=$(./docker/docker-version-codex-builder-final.sh)" >>.env
cat <<EOF >>.env
CODEX_VERSION=$(./docker/docker-version-codex.sh)
CODEX_WHEEL=codex-${PKG_VERSION}-py3-none-any.whl
WHEELS=/wheels
EOF
