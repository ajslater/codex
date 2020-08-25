#!/bin/sh
# Fix as much as many linting issues as we can
poetry run isort --color .
poetry run black .
prettier --write .
