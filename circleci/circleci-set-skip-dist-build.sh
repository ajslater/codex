#!/bin/bash
set -eou pipefail
# shellcheck disable=SC1091
source .env.build
WHEEL_PATH=dist/codex-${PKG_VERSION}-py3-none-any.whl
if [ -f "$WHEEL_PATH" ]; then
    touch ./SKIP_STEPS
fi
