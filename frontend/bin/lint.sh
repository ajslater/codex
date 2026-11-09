#!/usr/bin/env bash
# Lint the Makefiles and shell scripts
set -euxo pipefail

uvx mbake@latest validate Makefile cfg/*.mk

bin/sh-tools.sh --lint

# Not .prettierignore: it lists *.sh, which would hide every script from roman.
uv run bin/roman.py -i .shellignore .
