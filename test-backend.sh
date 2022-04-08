#!/bin/bash
# Run all codex tests
set -euxo pipefail

cd "$(dirname "$0")"

poetry show django-dark
# shellcheck disable=2046
ls $(poetry env info -p)/lib/**/site-packages/dark/static/admin/css
./collectstatic.sh
ls codex/static_root/admin/css/dark*
poetry run pytest
# pytest-cov leaves .coverage.$HOST.$PID.$RAND files around while coverage itself doesn't
poetry run coverage erase || true
