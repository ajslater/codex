#!/bin/bash
# copy codex wheels to host cache
set -exuo pipefail
SERVICE_NAME=codex-wheels
CONTAINER_NAME=project_${SERVICE_NAME}_1
docker-compose pull ${SERVICE_NAME}
docker-compose create --no-build ${SERVICE_NAME}
docker container cp --follow-link ${CONTAINER_NAME}:/wheels ./cache/packages/
docker rm ${CONTAINER_NAME} || true
