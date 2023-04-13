#!/bin/bash
# install dependencies for hitting the hub.docker.com api directly
set -euxo pipefail

sudo apt-get update
sudo apt-get install curl jq
