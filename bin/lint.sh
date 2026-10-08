#!/usr/bin/env bash
# Lint checks
set -euxo pipefail

uvx mbake@latest validate Makefile cfg/*.mk

# Javascript, JSON, Markdown, YAML #####
bun run lint

bin/sh-tools.sh --lint

# Not .prettierignore: it lists *.sh, which would hide every script from roman.
uv run bin/roman.py -i .shellignore .
