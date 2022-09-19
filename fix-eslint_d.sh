#!/bin/bash
 # idk why but eslint_d can't find these packages without symlinks
set -euo pipefail

mkdir -p node_modules/eslint-plugin-no-constructor-bind/node_modules
cd node_modules/eslint-plugin-no-constructor-bind/node_modules
ln -sf ../../requireindex .
