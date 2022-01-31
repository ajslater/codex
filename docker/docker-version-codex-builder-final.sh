#!/bin/bash
# Compute the version tag for codex-builder-final
set -euo pipefail

source .env
source .env.versions
EXTRA_MD5S=(
    "$CODEX_BUILDER_BASE_VERSION  codex-builder-base-version"
    "$PKG_VERSION  codex-package-version")

# shellcheck disable=SC2046
DEPS=(
    "$0"
    builder-final.Dockerfile
    docker/docker-build-codex-builder-final.sh
)

source ./docker/docker-version-checksum.sh
