#!/bin/bash
# Compute the version tag for ajslater/codex-builder-base
set -euo pipefail
. ci/machine-env.sh
EXTRA_MD5S=("$CODEX_BASE_VERSION  codex-base-version")
DEPS=(
  "$0"
  ci/builder-base.Dockerfile
)

. ./ci/version-checksum.sh
