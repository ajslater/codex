#!/bin/bash
set -euxo pipefail
./test-ci-test.sh
export PLATFORMS="linux/arm64"
./build-wheels.sh
./build-codex.sh
