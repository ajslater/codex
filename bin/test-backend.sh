#!/bin/bash
# Run codex django tests
set -euxo pipefail

export PYTHONPATH=.
export DJANGO_TEST_PROCESSES=auto
# Django unit tests interfere with each other's database so cannot be run in parallel.
export UV_NO_DEV=1
cmd=(uv run --group test python3 -Wa bin/manage.py test)
if [ "${1:-}" ]; then
  cmd+=("${1}")
fi

"${cmd[@]}"
