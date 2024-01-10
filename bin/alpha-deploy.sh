#!/bin/bash
# Run alpha, test, build and deploy for a local release on one arch
set -euxo pipefail
# shellcheck disable=SC1091
./docker/docker-env.sh
./docker/docker-build-image.sh codex-base
./docker/docker-build-image.sh codex-builder-base
./bin/alpha-test-build-dist.sh
./docker/docker-build-image.sh codex
