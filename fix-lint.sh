#!/bin/bash
# Fix as much as many linting issues as we can
set -euxo pipefail
poetry run isort --color .
poetry run black .
bash -c "cd frontend && npx eslint --fix ."
prettier --write .
