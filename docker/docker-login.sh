#!/bin/bash
set -euxo pipefail
# login to docker using environment variables
docker login --username="$DOCKER_USER" --password="$DOCKER_PASS"
