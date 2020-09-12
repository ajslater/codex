#!/bin/bash
set -euo pipefail
poetry publish -u "$PYPI_USER" -p "$PYPI_PASS"
