#!/bin/bash
# copy codex wheels to host cache
set -exuo pipefail
docker-compose pull codex-wheels
docker-compose create --no-build codex-wheels
docker container cp --follow-link codex-codex-wheels-1:/wheels ./cache/packages/
docker rm codex-codex-wheels-1
