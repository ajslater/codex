#!/bin/bash
set -euo pipefail
poetry export --dev --without-hashes |
    cat - \
        .dockerignore \
        docker-build-codex-wheels.sh \
        builder-requirements.txt \
        harvest_wheels.py \
        wheels.Dockerfile |
    md5sum |
    awk '{print $1}'
