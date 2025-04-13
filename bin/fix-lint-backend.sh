#!/bin/bash
# Fix common linting errors
set -euxo pipefail

################
# Ignore files #
################
bin/sortignore.sh

####################
###### Python ######
###################
uv run ruff check --fix .
uv run ruff format .
uv run djlint codex/templates --profile=django --reformat

############################################
##### Javascript, JSON, Markdown, YAML #####
############################################
npm run fix

###################
###### Shell ######
###################
shellharden --replace ./**/*.sh .env.platforms
