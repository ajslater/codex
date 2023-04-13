#!/bin/sh
# Open development server processes in macOS terminal tabs
# Requires npm ttab
# The Vue dev server
ttab -t "Codex Vue" "make dev-frontend-server"
# The API server
make dev-server
