#!/bin/bash
# Install shellcheck for the correct architecture
set -euo pipefail
DEST=/usr/local/bin
SRC=/vendor/shellcheck
echo "*** install shellcheck ***"
if [ "$TARGETPLATFORM" = "linux/amd64" ]; then
  apk add --no-cache shellcheck
elif [ "$TARGETPLATFORM" = "linux/arm64" ]; then
  cp $SRC/arm64/shellcheck $DEST
elif [ "$TARGETPLATFORM" = "linux/armv7" ]; then
  cp $SRC/armv7/shellcheck $DEST
fi
