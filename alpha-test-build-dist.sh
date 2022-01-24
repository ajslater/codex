#!/bin/bash
# Run CI test & build for a local alpha release
set -euxo pipefail
./docker-build-codex-builder.sh
CODEX_BUILDER_VERSION=$(./docker-version-codex-builder.sh)
export CODEX_BUILDER_VERSION
./docker/docker-compose-exit.sh codex-frontend-lint
./docker/docker-compose-exit.sh codex-frontend-test
./docker/docker-compose-exit.sh codex-frontend-build
./docker/docker-compose-exit.sh codex-backend-test
./docker/docker-compose-exit.sh codex-backend-lint
./docker/docker-compose-exit.sh codex-build-dist
