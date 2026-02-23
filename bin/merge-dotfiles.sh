#!/usr/bin/env bash
# Merge development environment dotfiles
set -euo pipefail
SRC=$1
DEST=$2
readonly FILES=(.*ignore .shellcheckrc)

created=0
skipped=0
merged=0
dest_files=()
for f in "${FILES[@]}"; do
  dest_f=$DEST/$f
  if [ ! -f "$dest_f" ]; then
    touch "$dest_f"
    ((created++)) || true
  fi
  if [ -L "$dest_f" ]; then
    ((skipped++)) || true
  else
    sort --mmap --unique --output="$dest_f" "$SRC/$f" "$dest_f"
    dest_files+=("$dest_f")
    ((merged++)) || true
  fi
done
echo -n "Merged dotfiles:"
if ((created)); then
  echo -n " $created created"
fi
if ((skipped)); then
  echo -n " $skipped skipped"
fi
if ((merged)); then
  echo -n " $merged merged"
fi
echo ""
git status --short "${dest_files[@]}"
