#!/usr/bin/env bash
# Delete all files listed in the delete.txt file
set -euo pipefail
DEVENV=$1
DELETE_FILE=$DEVENV/delete.txt
existing_files=()
while IFS= read -r file || [[ -n "$file" ]]; do
  [[ -z "$file" || "$file" == \#* ]] && continue
  [[ -f "$file" ]] && existing_files+=("$file")
done <"$DELETE_FILE"

echo "Deleting ${#existing_files[@]} files..."
rm -f -- "${existing_files[@]}"
