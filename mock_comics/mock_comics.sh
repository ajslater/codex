#!/bin/bash
# create a mock comics
# mock_comics.sh <root> <num>
set -euo pipefail
poetry run ./mock_comics.py "$@"
