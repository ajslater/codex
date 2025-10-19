#!/bin/bash
# Run prettier on nginx files because overrides doesn't work yet.
set -euxo pipefail
CONFIG_DIR=ci/nginx/http.d/codex
if [ -d "$CONFIG_DIR" ]; then
  prettier --parser nginx "$CONFIG_DIR/*.conf" "$@"
fi
