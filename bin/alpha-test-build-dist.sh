#!/bin/bash
# Run CI test & build for a local alpha release
set -euxo pipefail
./docker/docker-build-image.sh codex-dist-builder
./docker/docker-compose-exit.sh codex-save-cache
./docker/docker-compose-exit.sh codex-frontend-lint
./docker/docker-compose-exit.sh codex-frontend-test
./docker/docker-compose-exit.sh codex-frontend-build
./docker/docker-compose-exit.sh codex-backend-test
./docker/docker-compose-exit.sh codex-backend-lint
./docker/docker-compose-exit.sh codex-build-dist
