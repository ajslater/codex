#!/usr/bin/env bash
# Fix common linting errors with docker
set -euxo pipefail

#######################
###### Dockerfile #####
#######################
mapfile -t dockerfiles < <(find . -maxdepth 1 -type f -name '*Dockerfile')
if [ ${#dockerfiles[@]} -gt 0 ]; then
  dockerfmt --write "${dockerfiles[@]}"
fi
