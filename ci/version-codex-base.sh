#!/bin/bash
# Compute the version tag for codex-base
set -euo pipefail
EXTRA_MD5S=("x x")

DEPS=(
  "$0"
  .dockerignore
  ci/base.Dockerfile
  ci/debian.sources
  ci/docker-build-image.sh
  ci/machine-arch.sh
  ci/version-checksum.sh
  ci/versions-create-env.sh
  ci/versions-env-filename.sh
  docker-bake.hcl
)

. ./ci/version-checksum.sh
