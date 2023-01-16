#!/bin/bash
# echo the arch specific .env filename
set -euo pipefail
ENV_FN=./.env
if [ "${CIRCLECI-}" ]; then
    ARCH=$(./docker/docker-arch.sh)
    ENV_FN=${ENV_FN}-${ARCH}
fi
echo "$ENV_FN"
