#!/bin/bash
# Set version in all three places: Frontend, API, & Docker Env.
set -euo pipefail
VERSION="$1"

# BSD sed behaves differently
if [ "$(uname)" = "Darwin" ]; then
    sedi=('/usr/bin/sed' '-i' '')
else
    sedi=('sed' '-i')
fi

"${sedi[@]}" "s/PKG_VERSION=.*/PKG_VERSION=$VERSION/" .env
poetry version "$VERSION"
cd frontend
npm version --allow-same-version "$VERSION"
