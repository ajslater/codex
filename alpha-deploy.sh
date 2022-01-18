#!/bin/bash
# Run alpha, test, build and deploy  for a local release on one arch
set -euxo pipefail
./alpha-test-build-dist.sh
# XXX PLATFORMS declaration current broken for wheels because build-codex bake does not see local wheel image
./build-wheels.sh
export PLATFORMS="linux/amd64"
./build-codex.sh
