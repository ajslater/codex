#!/usr/bin/env bash
# Run remark but not when in a claude workspace
set -euo pipefail
echo "$PWD" | grep -q '.claude' && exit 0 || bun remark --quiet .
