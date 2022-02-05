#!/bin/bash
# Run alpha, test, build and deploy  for a local release on one arch
set -euxo pipefail
# shellcheck disable=SC1091
source .env.pushover
export PUSHOVER_API_TOKEN
export PUSHOVER_USER_ID
# shellcheck disable=SC1091
source .env.build
catch() {
    poetry run pushover -s1 "$PKG_VERSION failed"
}
trap 'catch' ERR
./docker/docker-env.sh
./docker/docker-build-image.sh codex-base
./docker/docker-build-image.sh codex-builder-base
./alpha-test-build-dist.sh
# XXX PLATFORMS declaration current broken for wheels because build-codex bake does not see local wheel image
# https://github.com/docker/cli/issues/3286
export PLATFORMS="linux/amd64"
./docker/docker-build-image.sh codex
poetry run pushover -s$? "$PKG_VERSION success"
