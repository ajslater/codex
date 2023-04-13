#!/bin/bash
# Run CI test & build for a local alpha release
set -euxo pipefail
./bin/docker/docker-build-image.sh codex-dist-builder
./bin/docker/docker-compose-exit.sh codex-save-cache
./bin/docker/docker-compose-exit.sh codex-frontend-lint
./bin/docker/docker-compose-exit.sh codex-frontend-test
./bin/docker/docker-compose-exit.sh codex-frontend-build
./bin/docker/docker-compose-exit.sh codex-backend-test
./bin/docker/docker-compose-exit.sh codex-backend-lint
./bin/docker/docker-compose-exit.sh codex-build-dist
