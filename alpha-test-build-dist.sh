#!/bin/bash
# Run CI test & build for a local alpha release
set -euxo pipefail
CODEX_BASE_VERSION=$(./docker-version-codex-base.sh)
export CODEX_BASE_VERSION
CODEX_BUILDER_BASE_VERSION=$(./docker-version-codex-builder-base.sh)
export CODEX_BUILDER_BASE_VERSION
CODEX_DIST_BUILDER_VERSION=$(./docker-version-codex-dist-builder.sh)
export CODEX_DIST_BUILDER_VERSION
CODEX_BUILDER_FINAL_VERSION=$(./docker-version-codex-builder-final.sh)
export CODEX_BUILDER_FINAL_VERSION
./docker-build-codex-dist-builder.sh
./docker/docker-compose-exit.sh codex-save-cache
./docker/docker-compose-exit.sh codex-frontend-lint
./docker/docker-compose-exit.sh codex-frontend-test
./docker/docker-compose-exit.sh codex-frontend-build
./docker/docker-compose-exit.sh codex-backend-test
./docker/docker-compose-exit.sh codex-backend-lint
./docker/docker-compose-exit.sh codex-build-dist
