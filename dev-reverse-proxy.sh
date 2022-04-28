#!/bin/bash
# Run an nginx reverse proxy with a subpath for development testing
set -euo pipefail
cd "$(dirname "$0")" || exit 1
docker-compose -f nginx/nginx.yaml up
