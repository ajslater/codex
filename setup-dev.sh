#!/bin/sh
# Set up development dependancies
echo "*** install API build dependencies ***"
pip3 install -U poetry
poetry install --no-root

echo "*** install frontend build dependencies ***"
bash -c "cd frontend && npm install"

echo "*** copy choices from frontend ***"
cp frontend/src/choices/* codex/choices/
