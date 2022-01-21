#!/bin/bash
set -euo pipefail
source .env
echo "$PYTHON_ALPINE_VERSION" |
    cat - \
        .dockerignore \
        base.Dockerfile \
        docker-build-codex-base.sh |
    md5sum |
    awk '{print $1}'
