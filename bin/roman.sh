#!/bin/bash
# Find all shell scripts without a first line comment.
# Created due to working with @defunctzombie
set -uo pipefail

# set options
if [ "$1" = "-i" ]; then
  shift
  ignorefile=$1
  shift
fi

# check for paths
if [ "$1" = "" ]; then
  echo "Usage: $0 [options] <path> [path...]"
  echo "Options:"
  echo -e "\t-i <ignorefile>"
  exit 1
fi

if command -v ggrep &> /dev/null; then
  GREP_CMD=$(command -v ggrep)
else
  GREP_CMD=$(command -v grep)
fi
# get files
fns=$(find "$@" -type f -name "*.sh")
if [ "$ignorefile" ]; then
  fns=$(echo "$fns" | "$GREP_CMD" -vf "$ignorefile")
fi

# find nonconforming files
good=1
while read -ra fn; do
  # sc doesn't understand that fn isn't an array
  # shellcheck disable=2128
  bad=$(sed -n '2 p' < "$fn" | "$GREP_CMD" -v '^# +*')
  if [ "$bad" ]; then
    # shellcheck disable=2128
    echo "🔪 $fn"
    good=0
  fi
done < <(echo "$fns")

if [ "$good" = 0 ]; then
  exit 1
fi
echo 👍
