#!/bin/sh
# Convenice script for running django manage tasks under poetry
export DJANGO_SETTINGS_MODULE="codex.settings.settings"
poetry run python3 manage.py "$@"
