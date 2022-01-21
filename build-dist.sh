#!/bin/bash
# Build script for producing a codex python package
set -euxo pipefail
cd "$(dirname "$(readlink "$0")")"
source circleci-build-skip.sh

export LOGLEVEL=VERBOSE
./pm check
echo "*** build and package application ***"
poetry build
