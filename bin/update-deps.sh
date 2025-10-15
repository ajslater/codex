#!/bin/bash
# Update python and npm dependencies
set -euo pipefail
uv sync --no-install-project --all-extras --all-groups --all-packages --upgrade
uv tree --depth 1 --outdated | grep "latest" || true
npm update
npm outdated
bash -c "cd frontend && bin/update-deps.sh"
