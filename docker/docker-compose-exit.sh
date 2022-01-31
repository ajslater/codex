#!/bin/bash
# Run a docker compose service and return its exit code
set -euo pipefail
./circleci/circleci-step-halt.sh
source .env
export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
# docker compose without the dash doesn't have the exit-code-from param
docker-compose up --exit-code-from "$1" "$1"
