#!/bin/sh
# Open all three development server processes in macOS terminal tabs
# requires npm ttab
CODEX_DIR="$(dirname "$0")"
CODEX_VUE_DIR="${CODEX_DIR}/codex_vue"

# The API server
ttab -t "Codex Django" "cd $CODEX_DIR && DEV=1 ./run-server.sh"
# Django livereload server for Django HMR
ttab -t "Codex Django livereload" "cd $CODEX_DIR && DEV=1 ./pm livereload"
# The Vue dev server
ttab -t "Codex Vue"  "cd $CODEX_VUE_DIR && npm run dev"
