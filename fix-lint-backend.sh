#!/bin/bash
set -euxo pipefail
# Fix common linting errors
####################
###### Python ######
###################
poetry run isort --color .
poetry run black .

############################################
##### Javascript, JSON, Markdown, YAML #####
############################################
npx eslint . --ext .cjs,.mjs,.js,.json,.md,.yaml --fix
npx prettier --write .

###################
###### Shell ######
###################
shfmt -s -w -i 4 ./*.sh ./**/*.sh
