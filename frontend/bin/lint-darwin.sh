#!/usr/bin/env bash
# Lint checks
set -euxo pipefail

if [ "$(uname)" != "Darwin" ]; then
  # subdirs aren't copied into docker builder
  # .env files aren't copied into docker
  exit 0
fi
bin/lint-sh.sh
