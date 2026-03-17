#!/usr/bin/env bash
# Compute the version tag for ajslater/codex-dist-builder
set -euo pipefail
. ./ci/machine-env.sh
EXTRA_MD5S=("$CODEX_BUILDER_BASE_VERSION  codex-builder-base-version")

# shellcheck disable=SC2046
readarray -d '' SOURCE_DEPS < <(find cfg codex frontend tests -type f \( \
  ! -path "*node_modules*" \
  ! -path "*codex/static_build*" \
  ! -path "*codex/static*" \
  ! -name "*~" \
  ! -name "*.pyc" \
  ! -name ".*cache" \
  ! -name ".DS_Store" \
  -print0 \
  \))
DEPS=(
  "$0"
  .prettierignore
  .shellcheckrc
  bin/build-dist.sh
  bin/collectstatic.sh
  bin/lint-python.sh
  bin/lint-complexity.sh
  bin/lint.sh
  bin/manage.py
  bin/pm
  bin/roman.py
  bin/test-python.sh
  bin/test.sh
  ci/dist-builder.Dockerfile
  eslint.config.js
  package.json
  package-lock.json
  pyproject.toml
  uv.lock
  Makefile
  "${SOURCE_DEPS[@]}"
)

. ./ci/version-checksum.sh
