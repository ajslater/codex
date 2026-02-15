#!/usr/bin/env bash
# Update python dependencies
set -euo pipefail
uv sync --no-install-project --all-extras --all-groups --all-packages --upgrade
uv tree --all-groups --depth 1 --upgrade --outdated | grep --color=always "(latest:.*)" || true
