#!/bin/bash
# Build script for producing a codex python package
set -euxo pipefail
cd "$(dirname "$(readlink "$0")")"

echo "*** build frontend ***"
rm -rf "codex/static_build"
bash -c "cd frontend && npm run build"

echo "*** collect static resources into static root ***"
export LOGLEVEL=VERBOSE
./collectstatic.sh
./pm check
echo "*** build and package application ***"
poetry build
