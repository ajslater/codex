#!/bin/bash
set -euo pipefail
poetry run python3 manage.py "$@"
