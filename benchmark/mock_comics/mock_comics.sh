#!/bin/bash
# create a mock comics
# mock_comics.sh <root> <num>
set -euo pipefail
uv run ./mock_comics.py "$@"
