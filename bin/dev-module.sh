#!/usr/bin/env bash
# Run a main method in an arbitrary module
set -euxo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
# Only an unset DEBUG defaults on; DEBUG= or DEBUG=0 turns it off.
export DEBUG="${DEBUG-1}"
case $DEBUG in
'' | 0 | false | False) ;;
*) export PYTHONDEVMODE=1 ;;
esac
export PYTHONDONTWRITEBYTECODE=1
uv run python3 "$@"
