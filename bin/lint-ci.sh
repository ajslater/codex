#!/usr/bin/env bash
# Lint checks for ci
set -euxo pipefail

# shellcheck source=bin/_lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

# Every workflow, so ci.yml's calls into the devenv-* workflows are checked.
if [[ -d .github/workflows ]] && need actionlint; then
  actionlint
fi
