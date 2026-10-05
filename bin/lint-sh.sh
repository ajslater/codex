#!/usr/bin/env bash
# Lint shell scripts
set -euxo pipefail

mapfile -d '' files < <("$(dirname "${BASH_SOURCE[0]}")/find-sh.sh")
# A failing finder must fail this script, not look like zero files.
wait "$!"
if ((${#files[@]} == 0)); then
  exit 0
fi

shellcheck --external-sources "${files[@]}"
shellharden --check "${files[@]}"
shfmt --simplify --indent 2 --diff "${files[@]}"
