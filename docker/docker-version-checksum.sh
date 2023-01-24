#!/bin/bash
# create an arched md5sum from a list of parts
set -euo pipefail
# This script must be sourced to pass these arrays in properly
# Params:
#   EXTRA_MD5S  double space separated array of md5s and labels
#   DEPS        array of dependencies
DEPS_MD5=$(md5sum "${DEPS[@]}")
ALL_MD5S=("${EXTRA_MD5S[@]}" "${DEPS_MD5[@]}")
VERSION=$(
    echo "${ALL_MD5S[@]}" \
        | LC_ALL=C sort -k 2 \
        | md5sum \
        | awk '{print $1}'
)
if [[ ${CIRCLECI-} ]]; then
    ARCH=$(./docker/docker-arch.sh)
    VERSION="${VERSION}-$ARCH"
fi
echo "$VERSION"
