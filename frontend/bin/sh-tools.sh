#!/usr/bin/env bash
# Fix or lint the shell scripts find-sh.sh lists: bin/sh-tools.sh --fix|--lint
# Both modes live here so the shellharden and shfmt flags cannot drift apart.
# A tool that is not installed is skipped with a message on stderr.
set -euxo pipefail

bin=$(dirname "${BASH_SOURCE[0]}")
# shellcheck source=bin/_lib.sh
. "$bin/_lib.sh"

case ${1:-} in
--fix)
  harden=--replace
  format=--write
  ;;
--lint)
  harden=--check
  format=--diff
  ;;
*)
  echo "usage: $0 --fix|--lint" >&2
  exit 2
  ;;
esac

load_files "$bin/find-sh.sh"
if ((${#files[@]} == 0)); then
  exit 0
fi

if [[ $1 == --lint ]] && need shellcheck; then
  shellcheck "${files[@]}"
fi
if need shellharden; then
  shellharden "$harden" "${files[@]}"
fi
if need shfmt; then
  shfmt --simplify --indent 2 "$format" "${files[@]}"
fi
