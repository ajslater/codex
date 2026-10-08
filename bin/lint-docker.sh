#!/usr/bin/env bash
# Lint checks for docker
set -euxo pipefail

bin=$(dirname "${BASH_SOURCE[0]}")
# shellcheck source=bin/_lib.sh
. "$bin/_lib.sh"

load_files "$bin/find-files.sh" -- -name '*Dockerfile'
if ((${#files[@]} == 0)); then
  exit 0
fi
if need hadolint; then
  hadolint "${files[@]}"
fi
if need dockerfmt; then
  dockerfmt --check "${files[@]}"
fi
