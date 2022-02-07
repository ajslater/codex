#!/bin/bash
set -eou pipefail
pip3 install --upgrade pip
pip3 install --requirement builder-requirements.txt
PKG_VERSION=$(./version.sh)
WHEEL_PATH=dist/codex-${PKG_VERSION}-py3-none-any.whl
if [ -f "$WHEEL_PATH" ]; then
    touch ./SKIP_STEPS
fi
