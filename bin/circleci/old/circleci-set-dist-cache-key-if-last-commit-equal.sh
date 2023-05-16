#!/bin/bash
# Is this current commit equal to the previous one
set -euo pipefail
FN=$1
A=$(git rev-list -n 1 HEAD^1)
B=$(git rev-list -n 1 HEAD) # $CIRCLE_SHA1
# shellcheck disable=SC2086
if git log --decorate --graph --oneline --cherry-mark --boundary "$A...$B" | grep "^+"; then
    echo "$A" >"$FN"
else
    echo "$B" >"$FN"
fi
