#!/usr/bin/env bash
# Run a docker compose service and return its exit code
set -euo pipefail
SERVICE=$1
# docker compose without the dash doesn't have the exit-code-from param
docker compose up --exit-code-from "$SERVICE" "$SERVICE"
