#!/bin/bash
set -euxo pipefail
./build-builder.sh
ci/docker-compose-exit.sh codex-lint
ci/docker-compose-exit.sh codex-test
ci/docker-compose-exit.sh codex-dist
export PLATFORMS="linux/amd64"
./build-multiarch.sh
