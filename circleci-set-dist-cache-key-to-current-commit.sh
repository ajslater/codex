#!/bin/bash
# Is this current commit equal to the previous one
set -euo pipefail
FN=$1
git rev-list -n 1 HEAD >"$FN"
