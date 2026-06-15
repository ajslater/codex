#!/usr/bin/env bash
# Lint checks for ci
set -euxo pipefail

if [ "$(uname)" != "Darwin" ]; then
  exit 0
fi

if [ -f .github/workflows/ci.yml ]; then
  actionlint .github/workflows/ci.yml
fi
