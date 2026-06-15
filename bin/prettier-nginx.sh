#!/usr/bin/env bash
# Run prettier on nginx files because overrides doesn't work yet.
set -euxo pipefail
CONFIG_DIR=nginx/http.d
if [ -d "$CONFIG_DIR" ]; then
  prettier --parser nginx "$CONFIG_DIR/*.conf" "$@"
fi
