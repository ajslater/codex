#!/bin/bash
# install poetry, for wheels-version.sh & deploy-pypi.sh
set -euo pipefail
pip3 install -U pip
pip3 install -U poetry
