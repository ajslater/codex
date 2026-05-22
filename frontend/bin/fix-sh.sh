#!/usr/bin/env bash
# Fix shell script formatting
set -euxo pipefail
shopt -s globstar

shellharden --replace ./**/*.sh
shfmt --simplify --write ./**/*.sh
