#!/bin/bash
# Run codex django tests
set -euxo pipefail

export PYTHONPATH=.
export DJANGO_TEST_PROCESSES=auto
# Django unit tests interfere with each other's database so cannot be run in parallel.
cmd=(uv run python3 -Wa bin/manage.py test)
if [ "${1:-}" ]; then
  cmd+=("tests.${1}")
fi

"${cmd[@]}"
