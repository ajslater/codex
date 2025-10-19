#!/bin/bash
# export env variables
export PATH=$PATH:"$HOME/.local/bin"
. ./ci/versions-env-filename.sh
set -a
# shellcheck disable=SC1090
. "$ENV_FN"
set +a
