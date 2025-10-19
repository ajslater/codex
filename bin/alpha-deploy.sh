#!/bin/bash
# Run alpha, test, build and deploy for a local release on one arch
set -euxo pipefail
# shellcheck disable=SC1091
./ci/versions-create-env.sh
./ci/docker-build-image.sh codex-base
./ci/docker-build-image.sh codex-builder-base
./bin/alpha-test-build-dist.sh
./ci/docker-build-image.sh codex
