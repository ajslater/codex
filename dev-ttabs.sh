#!/bin/sh
# Open development server processes in macOS terminal tabs
# Requires npm ttab
CODEX_DIR="$(dirname "$0")"
# The Vue dev server
ttab -t "Codex Vue" "$CODEX_DIR/dev-frontend.sh"
# The API server
DEBUG=1 "$CODEX_DIR"/dev-codex.sh
