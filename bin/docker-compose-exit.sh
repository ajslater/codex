#!/usr/bin/env bash
# Run one docker compose service and exit with its exit code, e.g. for CI
# Usage: bin/docker-compose-exit.sh <service>
set -euo pipefail
SERVICE=${1:?usage: bin/docker-compose-exit.sh <service>}
# docker compose without the dash doesn't have the exit-code-from param
docker compose up --exit-code-from "$SERVICE" "$SERVICE"
