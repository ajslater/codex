#!/bin/bash
# Publish codex to pypi
set -euo pipefail
pip3 install --upgrade pip
pip3 install --requirement builder-requirements.txt
poetry publish -u "$PYPI_USER" -p "$PYPI_PASS"
