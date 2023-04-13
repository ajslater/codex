#!/bin/bash
# Recreate the codex-dev container and enter it with a shell
set -euo pipefail
docker rm -f codex-dev || true
docker compose down
docker compose up codex-dev -d
