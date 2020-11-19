#!/bin/bash
# Buld script for producind a codex python package
set -euxo pipefail
cd "$(dirname "$(readlink "$0")")"

echo "*** build frontend ***"
rm -rf "codex/static_build"
cd frontend
npm run build

echo "*** collect static resources into static root ***"
cd ..
./collectstatic.sh


echo "*** build and package application ***"
# XXX poetry auto-excludes anything in gitignore. Dirty hack around that.
sed -i "s/.*static_root.*//" .gitignore
poetry build
git checkout .gitignore # XXX so i can run this locally
