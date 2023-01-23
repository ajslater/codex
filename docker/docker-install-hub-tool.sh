#!/bin/bash
# Install docker hub-tool
set -euxo pipefail

VERSION=0.4.5
URL="https://github.com/docker/hub-tool/releases/download/v${VERSION}/hub-tool-linux-amd64.tar.gz"

wget -c "$URL" -O - | tar xz -C /usr/local/bin/ --strip-components 1 hub-tool/hub-tool
