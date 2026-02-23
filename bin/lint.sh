#!/usr/bin/env bash
# Lint checks
set -euxo pipefail

# Javascript, JSON, Markdown, YAML #####
npm run lint

bin/lint-darwin.sh

uv run --group lint bin/roman.py -i .prettierignore .
