#!/usr/bin/env bash
# Sort all ignore files in place and remove duplicates
# Set locale to make output deterministic across shells
export LC_ALL=en_US.UTF-8
for f in .*ignore; do
  if [ ! -L "$f" ]; then
    sort --mmap --unique --output="$f" "$f"
    echo "$f" sorted
  fi
done
