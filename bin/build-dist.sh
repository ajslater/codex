#!/bin/bash
# Build script for producing a codex python package
set -euxo pipefail
cd "$(dirname "$0")"

export BUILD=1
make collectstatic
./bin/pm check
echo "*** build and package application ***"
PIP_CACHE_DIR=$(pip3 cache dir)
export PIP_CACHE_DIR
uv build
