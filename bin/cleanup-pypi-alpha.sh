#!/usr/bin/env bash
# Bulk-delete PEP 440 alpha releases (e.g. 1.2.3a4) from PyPI.
# Wraps pypi-cleanup: https://github.com/arcivanov/pypi-cleanup
#
# Usage:
#   bin/cleanup-pypi-alpha.sh <package>            # query-only (no auth, no deletion)
#   bin/cleanup-pypi-alpha.sh <package> --do-it    # delete; needs PYPI_CLEANUP_PASSWORD
#
# Auth (only required with --do-it):
#   PYPI_USERNAME           PyPI account username
#   PYPI_CLEANUP_PASSWORD   PyPI account password (read by pypi-cleanup directly)
set -euo pipefail

PACKAGE="${1:-}"
MODE="${2:-}"

if [ "$PACKAGE" = "" ]; then
  echo "Usage: $0 <package> [--do-it]" >&2
  exit 2
fi

# PEP 440 alpha suffix: 1.2.3a1, 1.2.3.alpha1, etc.
PATTERN='.*a\d+$'

if [ "$MODE" = "--do-it" ]; then
  : "${PYPI_USERNAME:?set PYPI_USERNAME}"
  : "${PYPI_CLEANUP_PASSWORD:?set PYPI_CLEANUP_PASSWORD}"
  uvx pypi-cleanup -p "$PACKAGE" -r "$PATTERN" -u "$PYPI_USERNAME" --do-it -y
else
  uvx pypi-cleanup -p "$PACKAGE" -r "$PATTERN" --query-only
fi
