#!/bin/bash
# Run an nginx reverse proxy with a subpath for development testing
set -euo pipefail
cd "$(dirname "$0")/nginx" || exit 1
docker-compose -f nginx.yaml up
