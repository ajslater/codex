#!/bin/bash
# Run CI test & build for a local alpha release
set -euxo pipefail
./build-builder.sh
./docker/docker-compose-exit.sh codex-lint
./docker/docker-compose-exit.sh codex-test
./docker/docker-compose-exit.sh codex-dist
