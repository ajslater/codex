#!/bin/bash
# Fix common linting errors
set -euxo pipefail
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
shellharden --replace ./*.sh ./**/*.sh
