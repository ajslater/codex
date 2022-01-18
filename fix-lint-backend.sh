#!/bin/bash
set -euxo pipefail
# Fix common linting errors
####################
###### Python ######
###################
poetry run isort --color .
poetry run black .

###################
###### Shell ######
###################
shfmt -s -w -i 4 ./*.sh ./**/*.sh
