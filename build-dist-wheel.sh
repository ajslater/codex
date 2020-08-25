#!/bin/sh
# Build pip installable wheel and sdist files from Dockerfile.build
docker-compose -f docker-compose-build.yaml up --build
