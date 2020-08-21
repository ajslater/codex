#!/bin/bash
set -euo pipefail
poetry run isort -rc --check-only .
poetry run black --check .
prettier --check .
hadolint Dockerfile
