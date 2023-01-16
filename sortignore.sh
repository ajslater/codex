#!/bin/bash
# Sort all ignore files in place and remove duplicates
for f in .*ignore; do
    sort --mmap --unique --output="$f" "$f"
done
