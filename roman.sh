#!/bin/bash
# Find all shell scripts without a first line comment.
# Created due to working with @defunctzombie

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

# get files
fns=$(find "$@" -type f -name "*.sh")
if [ "$ignorefile" ]; then
    fns=$(echo "$fns" | grep -v -f "$ignorefile")
fi

# find nonconforming files
good=1
while read -ra fn; do
    # sc doesn't understand that fn isn't an array
    # shellcheck disable=2128
    bad=$(sed -n '2 p' <"$fn" | grep -v '^#\ +*')
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
