#!/usr/bin/env bash
# Lint django templates
set -euxo pipefail

mapfile -t templates < <(find . -mindepth 1 -name '.*' -prune -o -path '*/templates/*' -name '*.html' -print)
if [ ${#templates[@]} -eq 0 ]; then
  echo "No django template files found. Nothing linted."
  exit 0
fi
uv run --group lint djlint --lint "${templates[@]}"
