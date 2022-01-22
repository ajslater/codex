#!/bin/bash
# Compute the version tag for ajslater/codex-wheels
set -euo pipefail
pip3 --quiet install --requirement builder-requirements.txt >&/dev/null
POETRY_EXPORT_MD5=$(poetry export --dev --without-hashes | md5sum)
DEPS=(
    "$0"
    .dockerignore
    builder-requirements.txt
    docker-build-codex-wheels.sh
    harvest_wheels.py
    wheels.Dockerfile
)
DEPS_MD5S=$(md5sum "${DEPS[@]}")
echo -e "$POETRY_EXPORT_MD5  poetry-export\n$DEPS_MD5S" \
    | LC_ALL=C sort \
    | md5sum \
    | awk '{print $1}'
