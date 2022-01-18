#!/bin/bash
# Build script for producing a codex python package
set -euxo pipefail
cd "$(dirname "$(readlink "$0")")"/frontend

echo "*** build frontend ***"
rm -rf ../codex/static_build/*
npm run build
