#!/usr/bin/env bash
# Shared helpers for bin/ scripts. Source it, do not run it.
# Bash 3.2 safe, as that is macOS's /bin/bash: no mapfile, namerefs or ${x^^}.

# Print an error and exit 1.
die() {
  echo "ERROR: $*" >&2
  exit 1
}

warn() {
  echo "WARNING: $*" >&2
}

is_darwin() {
  [[ $(uname) == Darwin ]]
}

# Succeed when the tool is on PATH. Otherwise say so and how to install it, and
# fail, so a caller can skip that tool visibly instead of silently.
need() {
  if command -v "$1" >/dev/null 2>&1; then
    return 0
  fi
  echo "skipped: $1 not installed (brew install $1)" >&2
  return 1
}

# Run a command and read its NUL-delimited output into the global array files.
# Fails with the command's status, so a broken finder cannot pass for zero
# files. A temp file stands in for mapfile -d '' and wait on a process
# substitution, which both need bash 4.4.
load_files() {
  local out file status=0
  out=$(mktemp)
  "$@" >"$out" || status=$?
  files=()
  if ((status == 0)); then
    while IFS= read -r -d '' file; do
      files+=("$file")
    done <"$out"
  fi
  rm -f "$out"
  return "$status"
}
