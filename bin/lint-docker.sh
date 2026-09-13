#!/usr/bin/env bash
# Lint checks for docker
set -euxo pipefail

if [ "$(uname)" != "Darwin" ]; then
  exit 0
fi
mapfile -t dockerfiles < <(find . -type f -name '*Dockerfile' -print -quit)
if [ ${#dockerfiles[@]} -gt 0 ]; then
  hadolint "${dockerfiles[@]}"
  dockerfmt --check "${dockerfiles[@]}"
fi
