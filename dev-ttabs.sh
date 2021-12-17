#!/bin/sh
# Open all three development server processes in macOS terminal tabs
# Requires npm ttab
CODEX_DIR="$(dirname "$0")"

# The API server
ttab -t "Codex Django" "DEBUG=1 $CODEX_DIR/dev-codex.sh"
# Django livereload server for Django HMR
ttab -t "Codex Django livereload" "$CODEX_DIR/dev-livereload.sh"
# The Vue dev server
ttab -t "Codex Vue" "$CODEX_DIR/dev-frontend.sh"
# An nginx reverse proxy with docker
ttab -t "Codex Nginx" "$CODEX_DIR/dev-reverse-proxy.sh"
