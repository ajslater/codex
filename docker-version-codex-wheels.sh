#!/bin/bash
set -euo pipefail
pip3 --quiet install --requirement builder-requirements.txt >&/dev/null
poetry export --dev --without-hashes |
    cat - \
        .dockerignore \
        docker-build-codex-wheels.sh \
        builder-requirements.txt \
        harvest_wheels.py \
        wheels.Dockerfile |
    md5sum |
    awk '{print $1}'
