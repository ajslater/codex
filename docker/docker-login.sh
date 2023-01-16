#!/bin/bash
# login to docker using environment variables
set -euo pipefail
echo "$DOCKER_PASS" | docker login --username="$DOCKER_USER" --password-stdin
