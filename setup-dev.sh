#!/bin/sh
# Set up development dependancies. Not used by build Dockerfile
echo "*** install system build dependencies ***"
pip3 install -U poetry
npm install -g prettier prettier-plugin-toml

echo "*** install API build dependencies ***"
poetry install --no-root

echo "*** install frontend build dependencies ***"
bash -c "cd frontend && npm install"

echo "*** copy choices from frontend ***"
cp frontend/src/choices/* codex/choices/
