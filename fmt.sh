#!/bin/bash
set -euo pipefail
poetry run isort -rc .
poetry run black .
