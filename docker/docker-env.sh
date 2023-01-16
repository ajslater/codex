#!/bin/bash
# create the docker .env firl for this architecture
set -euo pipefail
cd "$(dirname "$0")/.."
pip3 install --upgrade pip
pip3 install --requirement builder-requirements.txt
PKG_VERSION=$(./version.sh)
ENV_FN=$(./docker/docker-env-filename.sh)
rm -f "$ENV_FN"
# shellcheck disable=SC1091,SC2129
cat <<EOF >>"$ENV_FN"
PKG_VERSION=${PKG_VERSION}
CODEX_BASE_VERSION=$(./docker/docker-version-codex-base.sh)
EOF
echo "CODEX_BUILDER_BASE_VERSION=$(./docker/docker-version-codex-builder-base.sh)" >>"$ENV_FN"
echo "CODEX_DIST_BUILDER_VERSION=$(./docker/docker-version-codex-dist-builder.sh)" >>"$ENV_FN"
cat <<EOF >>"$ENV_FN"
CODEX_ARCH_VERSION=$(./docker/docker-version-codex-arch.sh)
CODEX_WHEEL=codex-${PKG_VERSION}-py3-none-any.whl
EOF
