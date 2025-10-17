#!/bin/bash
# Compute the version tag for ajslater/codex-builder-base
set -euo pipefail
. docker/machine-env.sh
EXTRA_MD5S=("$CODEX_BASE_VERSION  codex-base-version")
DEPS=(
  "$0"
  docker/builder-base.Dockerfile
)

. ./docker/docker-version-checksum.sh
