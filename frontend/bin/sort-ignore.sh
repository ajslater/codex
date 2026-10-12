#!/usr/bin/env bash
# Sort all ignore files in place and remove duplicates
# Negations (lines starting with !) go after every other line: git, docker and
# prettier let the last matching line win, so a negation only works after the
# patterns it overrides.
set -euo pipefail
# Bytewise order: every machine has the C locale, and it is the codepoint
# order merge_dotfiles.py sorts in, so the two never reorder each other.
export LC_ALL=C
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
