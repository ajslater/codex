#!/bin/bash
# create an arched md5sum from a list of parts
VERSION=$(
  cat - |
  LC_ALL=C sort |
  md5sum |
  awk '{print $1}'
)
 if [[ ${CIRCLECI:-} ]]; then
   ARCH=$(./docker/docker-arch.sh)
   VERSION="${VERSION}-$ARCH"
fi
echo "$VERSION"
