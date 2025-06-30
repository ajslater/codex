#!/bin/bash
# Run codex django tests
set -euxo pipefail

TEST_LIST=("test_asgi" "test_models" "test_importer.TestImporterBasic" "test_importer.TestImporterUpdateNone" "test_importer.TestImporterUpdateAll")
export PYTHONPATH=.
export DJANGO_TEST_PROCESSES=auto
# Django unit tests interfere with each other's database so cannot be run in parallel.
if [ "${1:-}" ]; then
  TEST_LIST=("$1")
fi

for test in "${TEST_LIST[@]}"; do
  uv run python3 -Wa bin/manage.py test "tests.${test}"
done
