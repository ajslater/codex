#!/usr/bin/env bash
# List files to fix and lint, minus an ignore file's patterns, NUL-delimited
#
# Usage: bin/find-files.sh [-i IGNOREFILE] [-- PREDICATE...]
#   e.g. bin/find-files.sh -- -name '*Dockerfile'
#
# Prints every regular file under the current directory that the find
# PREDICATEs match (every file without any) as `find` prints it
# (./path/to/file), sorted bytewise, each followed by a NUL. Skips what
# IGNOREFILE excludes, ./.shellignore by default. A missing default file
# excludes nothing; a missing -i file is an error.
#
# The ignore file holds one pattern per line:
#   - Blank lines and lines starting with # are ignored.
#   - A leading ! re-includes what an earlier pattern excluded.
#   - A leading ./ or / and a trailing / are stripped.
#   - A pattern with a / is anchored to this directory: a/b matches ./a/b but
#     not ./x/a/b.
#   - A pattern without a / matches a file or directory name at any depth.
#   - * ? and [...] are glob characters. As in find -path, * also matches /.
#
# Excluded directories are pruned, never descended. Like gitignore, a file
# under an excluded directory cannot be re-included, so ! only helps when it
# names the pruned directory itself: `.*` then `!.github` keeps ./.github
# and everything in it.
#
# Portable to BSD and GNU find: only -mindepth -name -path -prune -type
# -print0 -o ! and parentheses, plus whatever PREDICATEs the caller passes.
set -euo pipefail

usage() {
  echo "usage: $0 [-i IGNOREFILE] [-- PREDICATE...]" >&2
  exit 2
}

ignore_file=.shellignore
while getopts i: opt; do
  case $opt in
  i)
    ignore_file=$OPTARG
    if [[ ! -f $ignore_file ]]; then
      echo "$0: no ignore file $ignore_file" >&2
      exit 2
    fi
    ;;
  *) usage ;;
  esac
done
shift $((OPTIND - 1))

ignore_tests=()
keep_tests=()

if [[ -f $ignore_file ]]; then
  while read -r line || [[ -n $line ]]; do
    line=${line//$'\r'/}
    case $line in
    '' | '#'*) continue ;;
    esac

    negated=false
    if [[ $line == '!'* ]]; then
      negated=true
      line=${line#!}
    fi
    line=${line#./}
    line=${line#/}
    line=${line%/}
    if [[ -z $line ]]; then
      continue
    fi

    if [[ $line == */* ]]; then
      match=(-path "./$line")
    else
      match=(-name "$line")
    fi

    if [[ $negated == true ]]; then
      if ((${#keep_tests[@]})); then
        keep_tests+=(-o)
      fi
      keep_tests+=("${match[@]}")
    else
      if ((${#ignore_tests[@]})); then
        ignore_tests+=(-o)
      fi
      ignore_tests+=("${match[@]}")
    fi
  done <"$ignore_file"
fi

find_args=(. -mindepth 1)
if ((${#ignore_tests[@]})); then
  prune=(\( "${ignore_tests[@]}" \))
  if ((${#keep_tests[@]})); then
    prune+=(! \( "${keep_tests[@]}" \))
  fi
  find_args+=(\( "${prune[@]}" \) -prune -o)
fi
find_args+=(-type f)
if (($#)); then
  find_args+=(\( "$@" \))
fi
find_args+=(-print0)

find "${find_args[@]}" | LC_ALL=C sort -z
