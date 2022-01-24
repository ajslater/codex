#!/bin/sh
set -eu
export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
# docker compose without the dash doesn't have the exit-code-from param
docker-compose up --exit-code-from "$1" "$1"
