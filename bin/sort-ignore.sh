#!/usr/bin/env bash
# Sort all ignore files in place and remove duplicates
for f in .*ignore; do
  if [ ! -L "$f" ]; then
    sort --mmap --unique --output="$f" "$f"
    echo "$f" sorted
  fi
done
