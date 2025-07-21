#!/bin/bash
# Update python and npm dependencies
set -euo pipefail
uv sync --no-install-project --all-extras --upgrade
# uv tree --outdated | grep "^├.*latest" || true
uv lock --upgrade --dry-run
npm update
npm outdated
bash -c "cd frontend && bin/update-deps.sh"
