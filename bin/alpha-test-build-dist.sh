#!/bin/bash
# Run CI test & build for a local alpha release
set -euxo pipefail
./ci/docker-build-image.sh codex-dist-builder
./ci/docker-compose-exit.sh codex-save-cache
./ci/docker-compose-exit.sh codex-frontend-lint
./ci/docker-compose-exit.sh codex-frontend-test
./ci/docker-compose-exit.sh codex-frontend-build
./ci/docker-compose-exit.sh codex-backend-test
./ci/docker-compose-exit.sh codex-backend-lint
./ci/docker-compose-exit.sh codex-build-dist
