#!/bin/bash
# Run alpha, test, build and deploy for a local release on one arch
set -euxo pipefail
# shellcheck disable=SC1091
./bin/docker/docker-env.sh
./bin/docker/docker-build-image.sh codex-base
./bin/docker/docker-build-image.sh codex-builder-base
./bin/alpha-test-build-dist.sh
./bin/docker/docker-build-image.sh codex
