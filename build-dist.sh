#!/bin/bash
# Build script for producing a codex python package
set -euxo pipefail
cd "$(dirname "$0")"

./collectstatic.sh
./pm check
echo "*** build and package application ***"
PIP_CACHE_DIR=$(pip3 cache dir)
export PIP_CACHE_DIR
poetry build
