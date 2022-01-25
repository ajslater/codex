#!/bin/sh
# Set up development dependencies. Not used by build Dockerfile
echo "*** install system build dependencies ***"
pip3 install --upgrade poetry
npm install

echo "*** install API build dependencies ***"
poetry install --no-root --remove-untracked

echo "*** install frontend build dependencies ***"
bash -c "cd frontend && npm install"
