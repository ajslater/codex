#!/bin/bash
# Run a docker compose service and return its exit code
set -euo pipefail
#ENV_FN=$(./docker/docker-env-filename.sh)
# shellcheck disable=SC1090
#source "$ENV_FN"
#export CODEX_BUILDER_BASE_VERSION
#export CODEX_DIST_BUILDER_VERSION
#export CODEX_WHEEL
#export PKG_VERSION
docker compose up --exit-code-from "$1" "$1"
