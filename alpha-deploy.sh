#!/bin/bash
# Run alpha, test, build and deploy  for a local release on one arch
set -euxo pipefail
./alpha-test-build-dist.sh
export PLATFORMS="linux/amd64"
./build-wheels.sh
./build-codex.sh
