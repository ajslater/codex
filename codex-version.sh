#!/bin/bash
# Set version in all three places: Frontend, API, & Docker Env.
set -euo pipefail
VERSION="$1"
sed -i -e "s/PKG_VERSION=.*/PKG_VERSION=v$VERSION/" ./docker-env 
poetry version "$VERSION"
cd frontend
npm version --allow-same-version "$VERSION"
