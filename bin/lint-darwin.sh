#!/usr/bin/env bash
# Lint checks
set -euxo pipefail

if [ "$(uname)" != "Darwin" ]; then
  exit 0
fi
mbake validate Makefile
shellharden --check ./**/*.sh
# subdirs aren't copied into docker builder
# .env files aren't copied into docker
shellcheck --external-sources ./**/*.sh
if [ "$(find . -type f -name '*Dockerfile' -print -quit)" != "" ]; then
  hadolint ./*Dockerfile          #./**/*Dockerfile
  dockerfmt --check ./*Dockerfile #./**/*Dockerfile
fi
if [ -f .circleci/config.yml ]; then
  circleci config validate .circleci/config.yml
fi
