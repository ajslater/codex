#!/usr/bin/env bash
# Lint django templates
set -euxo pipefail

bin=$(dirname "${BASH_SOURCE[0]}")
# shellcheck source=bin/_lib.sh
. "$bin/_lib.sh"

load_files "$bin/find-files.sh" -- -path '*/templates/*' -name '*.html'
if ((${#files[@]} == 0)); then
  echo "No django template files found. Nothing linted."
  exit 0
fi
uv run --group lint djlint --lint "${files[@]}"
