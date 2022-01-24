#!/bin/bash
# Compute the version tag for ajslater/codex-wheels
set -euo pipefail
CODEX_BUILDER_BASE_VERSION=$(./docker-version-codex-builder-base.sh)
pip3 --quiet install --requirement builder-requirements.txt >&/dev/null
POETRY_EXPORT_MD5=$(poetry export --dev --without-hashes | md5sum)
DEPS=(
    "$0"
    .dockerignore
    docker-build-codex-wheels.sh
    harvest_wheels.py
    wheels.Dockerfile
)
DEPS_MD5S=$(md5sum "${DEPS[@]}")
VERSION=$(echo -e "$CODEX_BUILDER_BASE_VERSION  codex-builder-base-version\n$POETRY_EXPORT_MD5  poetry-export\n$DEPS_MD5S" |
    LC_ALL=C sort |
    md5sum |
    awk '{print $1}')
if [[ ${CIRCLECI:-} ]]; then
    VERSION="${VERSION}-$(uname -m)"
fi
echo "$VERSION"
