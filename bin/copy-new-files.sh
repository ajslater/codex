#!/usr/bin/env bash
# Usage: ./copy-new-files.sh SOURCE_DIR DEST_DIR
set -euo pipefail

SOURCE_DIR="${1:?Source directory required}"
DEST_DIR="${2:?Destination directory required}"

# Verify source directory exists
if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "Error: Source directory '$SOURCE_DIR' does not exist"
  exit 1
fi

# Create destination directory if it doesn't exist
mkdir -p "$DEST_DIR"

# Counter for copied files
copied=0
skipped=0

# Iterate through all files in source directory
dest_files=()
while read -r src_file; do
  # Get relative path from source directory
  rel_path="${src_file#"$SOURCE_DIR/"}"
  dest_file="$DEST_DIR/$rel_path"

  # Create destination subdirectory if needed
  dest_dir=$(dirname "$dest_file")
  mkdir -p "$dest_dir"

  # Check if destination file exists and compare contents
  if [[ -f "$dest_file" ]] && cmp -s "$src_file" "$dest_file"; then
    # echo "Skipping (identical): $rel_path"
    ((skipped++)) || true
  else
    # echo "Copying: $rel_path"
    cp -a "$src_file" "$dest_file"
    ((copied++)) || true
  fi
  dest_files+=("$dest_file")
done < <(find "$SOURCE_DIR" -type f ! -name '*~')

echo -n "Copied files:"
if ((copied)); then
  echo " $copied copied"
fi
if ((skipped)); then
  echo " $skipped skipped"
fi
echo ""
git status --short "${dest_files[@]}"
