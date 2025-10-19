#!/bin/bash
# Compute the version tag for codex-base
set -euo pipefail
EXTRA_MD5S=("x x")

DEPS=(
  "$0"
  .dockerignore
  ci/base.Dockerfile
  ci/debian.sources
  ci/docker-arch.sh
  ci/docker-build-image.sh
  ci/docker-env.sh
  ci/docker-env-filename.sh
  ci/docker-version-checksum.sh
  docker-bake.hcl
)

. ./ci/docker-version-checksum.sh
