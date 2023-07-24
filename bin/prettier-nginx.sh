#!/bin/bash
# Run prettier on nginx files because overrides doesn't work yet.
set -euo pipefail
CONFIG_DIR=bin/nginx/
prettier --parser nginx "$CONFIG_DIR"/http.d/codex/*.conf "$@"
