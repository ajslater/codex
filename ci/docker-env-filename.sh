#!/bin/bash
# Set the env filename var
ARCH=$(./ci/docker-arch.sh)
export ENV_FN=./.env-${ARCH}
