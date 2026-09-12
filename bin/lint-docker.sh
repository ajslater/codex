#!/usr/bin/env bash
# Lint checks for docker
set -euxo pipefail

if [ "$(uname)" != "Darwin" ]; then
  exit 0
fi
mapfile -t dockerfiles < <(find . -maxdepth 1 -type f -name '*Dockerfile')
if [ ${#dockerfiles[@]} -gt 0 ]; then
  hadolint "${dockerfiles[@]}"
  dockerfmt --check "${dockerfiles[@]}"
fi
