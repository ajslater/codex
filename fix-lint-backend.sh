#!/bin/bash
set -euxo pipefail
# Fix common linting errors
####################
###### Python ######
###################
poetry run isort --color .
poetry run black .
poetry run djlint codex/templates --profile=django --reformat

############################################
##### Javascript, JSON, Markdown, YAML #####
############################################
npm run fix

###################
###### Shell ######
###################
shfmt -s -w -i 4 ./*.sh ./**/*.sh
