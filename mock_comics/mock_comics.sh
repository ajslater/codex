#!/bin/bash
set -euo pipefail
poetry run ./mock_comics.py "$@"
