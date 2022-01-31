#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .env
ARCH=$(./docker/docker-arch.sh)
rm -f .env.versions
cat <<EOF >>.env.versions
CODEX_BASE_VERSION=$(./docker/docker-version-codex-base.sh)
EOF
cat <<EOF >>.env.versions
CODEX_BUILDER_BASE_VERSION=$(./docker/docker-version-codex-builder-base.sh)
EOF
cat <<EOF >>.env.versions
CODEX_DIST_BUILDER_VERSION=$(./docker/docker-version-codex-dist-builder.sh)
EOF
cat <<EOF >>.env.versions
CODEX_BUILDER_FINAL_VERSION=$(./docker/docker-version-codex-builder-final.sh)
EOF
cat <<EOF >>.env.versions
CODEX_VERSION=$(./docker/docker-version-codex.sh)
HOST_CACHE_DIR="./cache/packages/$ARCH"
CODEX_WHEEL=codex-${PKG_VERSION}-py3-none-any.whl
EOF
