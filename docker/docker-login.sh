#!/bin/bash
set -euo pipefail
# login to docker using environment variables
echo "$DOCKER_PASS" | docker login --username="$DOCKER_USER" --password-stdin
