#!/usr/bin/env bash
# Open development server processes in macOS terminal tabs
# Requires npm ttab
set -euo pipefail
# The Vue dev server
bunx ttab -t "Codex Vue" "make dev-frontend-server"
# The API server
make dev-server
