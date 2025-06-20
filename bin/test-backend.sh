#!/bin/bash
# Run codex django tests
set -euxo pipefail

export PYTHONPATH=.
export DJANGO_TEST_PROCESSES=auto
# Django unit tests interfere with each other's database for some reason
BUILD=1 uv run python3 -Wa bin/manage.py test tests.test_asgi
BUILD=1 uv run python3 -Wa bin/manage.py test tests.test_models
BUILD=1 uv run python3 -Wa bin/manage.py test tests.test_importer.TestImporterBasic
BUILD=1 uv run python3 -Wa bin/manage.py test tests.test_importer.TestImporterUpdateNone
BUILD=1 uv run python3 -Wa bin/manage.py test tests.test_importer.TestImporterUpdateAll
