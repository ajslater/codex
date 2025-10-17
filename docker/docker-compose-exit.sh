#!/bin/bash
# Run a docker compose service and return its exit code
. ./docker/machine-env.sh
docker compose up --exit-code-from "$1" "$1"
