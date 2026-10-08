#!/usr/bin/env bash
# Fix django template lint errors
set -euxo pipefail

bin=$(dirname "${BASH_SOURCE[0]}")
# shellcheck source=bin/_lib.sh
. "$bin/_lib.sh"

load_files "$bin/find-files.sh" -- -path '*/templates/*' -name '*.html'
if ((${#files[@]} == 0)); then
  echo "No django template files found. Nothing fixed."
  exit 0
fi
uv run --group lint djlint --reformat "${files[@]}"
