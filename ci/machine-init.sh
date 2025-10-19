#!/bin/bash
# Initialize environment for this machine.
set -euo pipefail
export PATH=$PATH:$HOME/.local/bin
./ci/circleci-step-halt.sh
./ci/machine-packages.sh
./ci/docker-init.sh
if [ $# -ne 0 ]; then
  ./ci/versions-create-env.sh "$@"
fi
. ./ci/machine-env.sh
