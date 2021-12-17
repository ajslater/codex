#!/bin/bash
set -euo pipefail
pip3 install -U pip
pip3 install -U poetry
poetry publish -u "$PYPI_USER" -p "$PYPI_PASS"
