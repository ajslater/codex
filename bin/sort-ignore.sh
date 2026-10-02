#!/usr/bin/env bash
# Sort all ignore files in place and remove duplicates
# Negations (lines starting with !) go after every other line: git, docker and
# prettier let the last matching line win, so a negation only works after the
# patterns it overrides.
set -euo pipefail
# Set locale to make output deterministic across shells
export LC_ALL=en_US.UTF-8
sorted=$(mktemp)
trap 'rm -f "$sorted"' EXIT
for f in .*ignore; do
  if [ -f "$f" ] && [ ! -L "$f" ]; then
    {
      sed '/^!/d' "$f" | sort --unique
      sed -n '/^!/p' "$f" | sort --unique
    } >"$sorted"
    # Write through the file, not over it, to keep its mode.
    cat "$sorted" >"$f"
    echo "$f" sorted
  fi
done
