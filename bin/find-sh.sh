#!/usr/bin/env bash
# List shell scripts to fix and lint, honoring .shellignore, NUL-delimited
#
# Prints every regular *.sh file, and every extensionless file whose first
# line is a sh or bash shebang (such as bin/pm), under the current directory
# as find prints it (./path/to/file.sh), sorted bytewise, each followed by a
# NUL. Skips what the optional ./.shellignore excludes; find-files.sh
# describes its syntax.
set -euo pipefail

shebang='^#![[:space:]]*([^[:space:]]*/)?(env[[:space:]]+)?(ba)?sh([[:space:]]|$)'

"$(dirname "${BASH_SOURCE[0]}")/find-files.sh" -- -name '*.sh' -o ! -name '*.*' |
  while IFS= read -r -d '' file; do
    if [[ $file != *.sh ]]; then
      line=''
      IFS= read -r line <"$file" || true
      [[ $line =~ $shebang ]] || continue
    fi
    printf '%s\0' "$file"
  done
