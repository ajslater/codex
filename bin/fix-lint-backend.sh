#!/bin/bash
# Fix common linting errors
set -euxo pipefail
# bin/sortignore.sh borks order for !ignores it think
####################
###### Python ######
###################
poetry run ruff check --fix .
poetry run ruff format .
poetry run djlint codex/templates --profile=django --reformat

############################################
##### Javascript, JSON, Markdown, YAML #####
############################################
npm run fix

###################
###### Shell ######
###################
shellharden --replace ./**/*.sh .env.platforms
