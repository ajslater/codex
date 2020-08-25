#!/bin/sh
# Build a codex docker image suitable for running from Dockerfile
. ./docker-env
docker build -t "$IMAGE" --build-arg "BASE_VERSION=$BASE_VERSION" --build-arg "PKG_VERSION=$PKG_VERSION" .
