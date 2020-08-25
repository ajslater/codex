#!/bin/bash
set -euo pipefail
source ./docker-env
docker save -o "$1" "$IMAGE"
