#!/bin/bash
# Install docker hub-tool
set -euxo pipefail

VERSION=0.4.5
URL="https://github.com/docker/hub-tool/releases/download/v${VERSION}/hub-tool-linux-amd64.tar.gz"
DEST="$HOME"

wget -c "$URL" -O - | tar xz -C "$DEST" --strip-components 1 hub-tool/hub-tool
chmod 755 "$DEST"/hub-tool
