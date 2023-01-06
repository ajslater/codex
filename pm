#!/bin/sh
# Convenience script for running django manage tasks under poetry
poetry run python3 manage.py "$@"
