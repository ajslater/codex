#!/bin/bash
# Initialize environment for this machine.
set -euo pipefail
./docker/circleci-step-halt.sh
./docker/machine-packages.sh
./docker/docker-init.sh
if [ $# -ne 0 ]; then
  ./docker/docker-env.sh "$@"
fi
