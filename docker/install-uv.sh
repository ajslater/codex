#!/bin/bash
# Install uv on circleci
set -euo pipefail
if which uv; then
  echo "uv already installed."
else
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
