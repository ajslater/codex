#!/bin/bash
# Install shellcheck for the correct architecture
set -euxo pipefail
echo "*** install shellcheck ***"
if [ "$TARGETPLATFORM" = "linux/amd64" ]; then
    apk add --no-cache shellcheck
    exit 0
fi

cd "$(dirname "$0")"
DEST=/usr/local/bin
if [ "$TARGETPLATFORM" = "linux/arm64" ]; then
    ls *
    cp arm64/shellcheck $DEST
elif [ "$TARGETPLATFORM" = "linux/armv7" ]; then
    cp armv7/shellcheck $DEST
fi
