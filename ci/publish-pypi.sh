#!/bin/bash
set -euo pipefail
DRY_RUN=$1
poetry publish -u "$PYPI_USER" -p "$PYPI_PASS" "$DRY_RUN"
