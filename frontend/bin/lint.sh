#!/usr/bin/env bash
# Lint checks
set -euxo pipefail

uv run mbake validate Makefile cfg/*.mk

# Javascript, JSON, Markdown, YAML #####
bun run lint

bin/lint-darwin.sh

uv run bin/roman.py -i .prettierignore .
