#!/bin/bash
# idk why but eslint_d can't find these packages without symlinks
set -euo pipefail

mkdir -p node_modules/eslint-plugin-markdownlint/node_modules
cd node_modules/eslint-plugin-markdownlint/node_modules/
ln -sf ../../markdownlint .

cd ../../..

cd frontend
./fix-eslint_d.sh
