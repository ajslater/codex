#!/usr/bin/env bash
# Lint checks for ci
set -euxo pipefail

# shellcheck source=bin/_lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

# Every workflow, so ci.yml's calls into the devenv-* workflows are checked.
# The files are named: bare actionlint finds them by a .git entry, and the CI
# image has none (.dockerignore). Given .git, named files are checked the same
# way, calls into local reusable workflows included; without it that one check
# is skipped.
shopt -s nullglob
files=(.github/workflows/*.yml .github/workflows/*.yaml)
if ((${#files[@]})) && need actionlint; then
  actionlint "${files[@]}"
fi
