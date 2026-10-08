#!/usr/bin/env bash
# Fix Dockerfile formatting
set -euxo pipefail

bin=$(dirname "${BASH_SOURCE[0]}")
# shellcheck source=bin/_lib.sh
. "$bin/_lib.sh"

load_files "$bin/find-files.sh" -- -name '*Dockerfile'
if ((${#files[@]})) && need dockerfmt; then
  dockerfmt --write "${files[@]}"
fi
