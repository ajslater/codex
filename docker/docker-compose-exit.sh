#!/bin/sh
set -eu
export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
CODEX_BASE_VERSION=$(./docker-version-codex-base.sh)
export CODEX_BASE_VERSION
CODEX_BUILDER_BASE_VERSION=$(./docker-version-codex-base.sh)
export CODEX_BUILDER_BASE_VERSION
CODEX_DIST_BUILDER_VERSION=$(./docker-version-codex-dist-builder.sh)
export CODEX_DIST_BUILDER_VERSION
docker compose pull "$1"
# docker compose without the dash doesn't have the exit-code-from param
docker-compose up --exit-code-from "$1" "$1"
