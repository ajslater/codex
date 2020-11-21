#!/bin/bash
set -euxo pipefail
# login to docker using environement variables
docker login --username="$DOCKER_USER" --password="$DOCKER_PASS"
