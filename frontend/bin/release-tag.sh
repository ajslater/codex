#!/usr/bin/env bash
# Merge main into develop and tag a release
set -euo pipefail
TAG=$1
git checkout main
git pull
git tag v"$TAG"
git push --tags
git checkout develop
git merge main --no-edit
git push
