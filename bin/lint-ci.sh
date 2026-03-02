#!/usr/bin/env bash
# Lint checks for ci
set -euxo pipefail

if [ "$(uname)" != "Darwin" ]; then
  exit 0
fi
if [ -f .circleci/config.yml ]; then
  circleci config validate .circleci/config.yml
fi
