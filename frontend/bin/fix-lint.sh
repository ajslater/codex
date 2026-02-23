#!/bin/bash
# Fix lints frontend
set -euo pipefail
npm run fix
uv run mbake format Makefile
