#!/usr/bin/env bash
# Lint shell scripts
set -euxo pipefail
shopt -s globstar

shellcheck --external-sources ./**/*.sh
shellharden --check ./**/*.sh
shfmt --simplify --diff ./**/*.sh
