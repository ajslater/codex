#!/bin/bash
# Sort all ignore files in place and remove duplicates
# Place ! exclusions at the end.
for fn in .*ignore; do
  if [ ! -L "$fn" ]; then
    output=$(
      grep -v '^!' "$fn" | sort --mmap --unique
      grep '^!' "$fn" | sort --mmap --unique
    )
    echo "$output" > "$fn"
  fi
done
