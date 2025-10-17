#!/bin/bash
# Compute the version tag for codex-base
set -euo pipefail
EXTRA_MD5S=("x x")

DEPS=(
  "$0"
  .dockerignore
  docker/base.Dockerfile
  docker/debian.sources
  docker/docker-arch.sh
  docker/docker-build-image.sh
  docker/docker-env.sh
  docker/docker-env-filename.sh
  docker/docker-version-checksum.sh
  docker-bake.hcl
)

. ./docker/docker-version-checksum.sh
