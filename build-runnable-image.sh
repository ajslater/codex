#!/bin/sh
# Build a codex docker image suitable for running from Dockerfile
. ./docker-env
docker build -t "$IMAGE" --build-arg "INSTALL_BASE_VERSION=$INSTALL_BASE_VERSION" --build-arg "RUNNABLE_BASE_VERSION=$RUNNABLE_BASE_VERSION" --build-arg "PKG_VERSION=$PKG_VERSION" .
