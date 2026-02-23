#!/usr/bin/env bash
# Lint checks
set -euxo pipefail

if [ "$(uname)" != "Darwin" ]; then
  exit 0
fi
shellharden --check ./**/*.sh
# subdirs aren't copied into docker builder
# .env files aren't copied into docker
shellcheck --external-sources ./**/*.sh
mapfile -t dockerfiles < <(find . -type f -name '*Dockerfile' -print -quit)
if [ ${#dockerfiles[@]} -gt 0 ]; then
  hadolint "${dockerfiles[@]}"
  dockerfmt --check "${dockerfiles[@]}"
fi
if [ -f .circleci/config.yml ]; then
  circleci config validate .circleci/config.yml
fi
