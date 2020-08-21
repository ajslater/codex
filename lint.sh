#!/bin/sh
# Lint checks
poetry run isort --check-only --color .
poetry run black --check .
prettier --check .
hadolint Dockerfile*
shellcheck ./*.sh
