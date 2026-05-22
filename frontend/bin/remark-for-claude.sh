#!/usr/bin/env bash
# Run remark but not when in a claude workspace
set -euo pipefail
if echo "$PWD" | grep -q '.claude'; then
	exit 0
fi
bun remark --quiet .
