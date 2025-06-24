#!/bin/bash
# Run codex django tests
set -euxo pipefail

export PYTHONPATH=.
export DJANGO_TEST_PROCESSES=auto
# Django unit tests interfere with each other's database so cannot be run in parallel.
uv run python3 -Wa bin/manage.py test tests.test_asgi
uv run python3 -Wa bin/manage.py test tests.test_models
uv run python3 -Wa bin/manage.py test tests.test_importer.TestImporterBasic
uv run python3 -Wa bin/manage.py test tests.test_importer.TestImporterUpdateNone
uv run python3 -Wa bin/manage.py test tests.test_importer.TestImporterUpdateAll
