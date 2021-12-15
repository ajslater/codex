#!/bin/bash
set -euxo pipefail
./ci-test.sh
export PLATFORMS="linux/amd64"
./build-multiarch.sh
