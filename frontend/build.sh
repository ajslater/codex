#!/bin/bash
# Build script for producing a codex python package
set -euxo pipefail
cd "$(dirname "$0")"

echo "*** build frontend ***"
rm -rf ../codex/static_build/*
npm run build
