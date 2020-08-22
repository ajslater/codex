#!/bin/bash
# setup script for circleci
set -xeuo pipefail
# TODO Could speed up ci by replacing this with an image

if [ -n "$CIRCLE_BRANCH" ]; then
    sudo apt-get install -y \
        gnupg2 \
        ca-certificates
    sudo cp docker/nodesource/nodesource.buster.list /etc/apt/sources.list.d/
    sudo apt-key add ./docker/nodesource/nodesource.gpg.key
    sudo apt-get update
    sudo apt-get install -y \
        build-essential \
        libffi-dev \
        libjpeg-dev \
        libssl-dev \
        libyaml-dev \
        nodejs \
        python3-pip \
        python3-venv \
        shellcheck \
        zlib1g-dev
fi

pip3 install -U poetry
poetry update
sudo npm install -g prettier
bash -c "cd frontend && npm install --no-optional"
cp frontend/src/choices/* codex/choices/
