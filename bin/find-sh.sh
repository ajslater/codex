#!/usr/bin/env bash
# List shell scripts to fix and lint, honoring .shellignore, NUL-delimited
#
# Prints every regular *.sh file under the current directory as `find` prints
# it (./path/to/file.sh), sorted bytewise, each followed by a NUL. Skips what
# the optional ./.shellignore excludes. A missing file excludes nothing.
#
# .shellignore holds one pattern per line:
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
# -print0 -o ! and parentheses.
set -euo pipefail

ignore_file=.shellignore
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
find_args+=(-type f -name '*.sh' -print0)

find "${find_args[@]}" | LC_ALL=C sort -z
