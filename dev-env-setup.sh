#!/bin/sh
# Set up development dependencies. Not used by build Dockerfile
echo "*** install system build dependencies ***"
pip3 install --upgrade pip
pip3 install --upgrade poetry
npm install

echo "*** install API build dependencies ***"
BREW_PREFIX=$(brew --prefix)
export LDFLAGS="-L${BREW_PREFIX}/opt/openssl@3/lib"
export CPPFLAGS="-I${BREW_PREFIX}/opt/openssl@3/include"
export PKG_CONFIG_PATH="${BREW_PREFIX}/opt/openssl@3/lib/pkgconfig"
poetry install --no-root --remove-untracked

echo "*** install frontend build dependencies ***"
cd frontend || exit 1
npm install
