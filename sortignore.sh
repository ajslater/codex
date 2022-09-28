#!/bin/bash
for f in .*ignore; do
    sort --mmap --unique --output="$f" "$f"
done
