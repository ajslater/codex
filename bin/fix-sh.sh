#!/usr/bin/env bash
# Fix shell script formatting
set -euxo pipefail

mapfile -d '' files < <("$(dirname "${BASH_SOURCE[0]}")/find-sh.sh")
# A failing finder must fail this script, not look like zero files.
wait "$!"
if ((${#files[@]} == 0)); then
  exit 0
fi

shellharden --replace "${files[@]}"
shfmt --simplify --indent 2 --write "${files[@]}"
