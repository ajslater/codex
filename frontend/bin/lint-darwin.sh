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
