#!/bin/bash
set -eou pipefail
PKG_VERSION=$(./version.sh)
WHEEL_PATH=dist/codex-${PKG_VERSION}-py3-none-any.whl
if [ -f "$WHEEL_PATH" ]; then
    touch ./SKIP_STEPS
fi
