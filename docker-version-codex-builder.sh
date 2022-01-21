#!/bin/bash
set -euo pipefail
CODEX_BASE_VERSION=$(./docker-version-codex-base.sh)
SHELLCHECK_MD5=$(find vendor/shellcheck -type f -exec md5sum {} + |
    LC_ALL=C sort |
    md5sum |
    awk '{print $1}')
echo "$CODEX_BASE_VERSION" "$SHELLCHECK_MD5" |
    cat - \
        .dockerignore \
        docker-build-codex-builder.sh \
        builder.Dockerfile \
        builder-requirements.txt |
    md5sum |
    awk '{print $1}'
