#!/usr/bin/env bash
# Compute the version tag for ajslater/codex-dist-builder
set -euo pipefail
. ./ci/machine-env.sh
EXTRA_MD5S=("$CODEX_BUILDER_BASE_VERSION  codex-builder-base-version")

# shellcheck disable=SC2046
readarray -d '' SOURCE_DEPS < <(find codex frontend tests -type f \( \
  ! -path "*node_modules*" \
  ! -path "*codex/static_build*" \
  ! -path "*codex/static_root*" \
  ! -name "*~" \
  ! -name "*.pyc" \
  ! -name ".eslintcache" \
  ! -name ".DS_Store" \
  -print0 \
  \))
DEPS=(
  "$0"
  .prettierignore
  .shellcheckrc
  ci/dist-builder.Dockerfile
  eslint.config.js
  bin/build-dist.sh
  bin/collectstatic.sh
  bin/lint-backend.sh
  bin/manage.py
  bin/pm
  bin/test-backend.sh
  package.json
  package-lock.json
  pyproject.toml
  uv.lock
  Makefile
  "${SOURCE_DEPS[@]}"
)

. ./ci/version-checksum.sh
