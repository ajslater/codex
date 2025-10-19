#!/bin/bash
# install and upgrade system packages.
set -euo pipefail
# uv
if which uv; then
  echo "uv already installed."
else
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

pip3 install --upgrade pip
