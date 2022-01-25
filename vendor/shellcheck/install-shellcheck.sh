#!/bin/bash
# Install shellcheck for the correct architecture
set -euxo pipefail
echo "*** install shellcheck ***"
if [ "$TARGETPLATFORM" = "linux/amd64" ]; then
    apk add --no-cache shellcheck
    exit 0
fi

cd "$(dirname "$0")"
DEST=/usr/local/bin/
if [ "$TARGETPLATFORM" = "linux/arm64" ]; then
    cp arm64/shellcheck $DEST
    PLATFORM=arm64
elif [ "$TARGETPLATFORM" = "linux/armv7" ]; then
    PLATFORM=armv7
else
  echo "Unhandled platform: $TARGETPLATFORM"
  exit 1
fi
cp $PLATFORM/shellcheck $DEST
