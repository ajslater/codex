#!/bin/bash
set -euo pipefail
if [ -n "${CIRCLECI:-}" ]; then
    source .env
    WHEEL_PATH=dist/codex-${PKG_VERSION}-py3-none-any.whl
    if [ -f "$WHEEL_PATH" ]; then
        echo "*** SKIP BUILD ***"
        exit 0
    fi
fi
