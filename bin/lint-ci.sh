#!/usr/bin/env bash
# Lint checks for ci
set -euxo pipefail

if [ "$(uname)" != "Darwin" ]; then
  exit 0
fi

# Every workflow, so ci.yml's calls into the devenv-* workflows are checked.
if [ -d .github/workflows ]; then
  actionlint
fi
