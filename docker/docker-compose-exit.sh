#!/bin/bash
# Run a docker compose service and return its exit code
. ./docker/machine-env.sh
#export CODEX_BUILDER_BASE_VERSION
#export CODEX_DIST_BUILDER_VERSION
#export CODEX_WHEEL
#export PKG_VERSION
docker compose up --exit-code-from "$1" "$1"
