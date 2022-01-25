#!/bin/bash
# Compute the version tag for ajslater/codex-builder
set -euo pipefail
CODEX_BUILDER_BASE_VERSION=$(./docker-version-codex-builder-base.sh)
# shellcheck disable=SC2046
read -ra SOURCE_DEPS <<<$(find codex frontend -type f \( -name ".*" ! -path "*node_modules*" ! -path "*codex/static_build*" ! -path "*codex/static_root*" ! -name "*~" ! -name "*.pyc" \))
DEPS=(
    "$0"
    .dockerignore
    .eslintrc.cjs
    .prettierignore
    .remarkignore
    .shellcheckrc
    builder.Dockerfile
    build-dist.sh
    build-frontend.sh
    collectstatic.sh
    lint.sh
    lint-backend.sh
    lint-frontend.sh
    manage.py
    package.json
    package-lock.json
    pm
    pyproject.toml
    poetry.lock
    setup.cfg
    test-backend.sh
    test-frontend.sh
    "${SOURCE_DEPS[@]}"
)
DEPS_MD5S=$(md5sum "${DEPS[@]}")
VERSION=$(echo -e "$CODEX_BUILDER_BASE_VERSION  codex-builder-base-version\n$DEPS_MD5S" |
    LC_ALL=C sort |
    md5sum |
    awk '{print $1}')
if [[ ${CIRCLECI:-} ]]; then
    VERSION="${VERSION}-$(uname -m)"
fi
echo "$VERSION"
