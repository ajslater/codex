#!/bin/bash
set -euo pipefail
URL=https://github.com/koalaman/shellcheck/releases/download/latest/shellcheck-latest.linux.aarch64.tar.xz
FN=shellcheck-latest/shellcheck
DEST=vendor/amd64/
wget --output-document=- $URL xz - $FN --directory $DEST >tar
