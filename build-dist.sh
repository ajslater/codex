#!/bin/bash
# Buld script for producind a codex python package
set -euxo pipefail
CODEX_DIR=$(dirname "$(readlink "$0")")

echo "*** build frontend ***"
rm -rf "$CODEX_DIR/static_build"
cd "$CODEX_DIR/frontend"
npm run build

echo "*** collect static resources into static root ***"
cd "$CODEX_DIR"
./collectstatic.sh


echo "*** build and package application ***"
# XXX poetry auto-excludes anything in gitignore. Dirty hack around that.
sed -i "s/.*static_root.*//" .gitignore
poetry build
git checkout .gitignore # XXX so i can run this locally
