#!/usr/bin/env bash
# Fix common linting errors with docker
set -euxo pipefail

#######################
###### Dockerfile #####
#######################
mapfile -t dockerfiles < <(find . -type f -name '*Dockerfile' -print -quit)
if [ ${#dockerfiles[@]} -gt 0 ]; then
  dockerfmt --write "${dockerfiles[@]}"
fi
