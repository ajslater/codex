#!/bin/bash
# Set the env filename var
ARCH=$(./ci/machine-arch.sh)
export ENV_FN=./.env-${ARCH}
