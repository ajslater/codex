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
export UV_NO_DEV=1
uv run --group lint ruff check --fix .
uv run --group lint ruff format .
uv run --group lint djlint codex/templates/*.html codex/templates/pwa/*.html --reformat

############################################
##### Javascript, JSON, Markdown, YAML #####
############################################
npm run fix

###################
###### Shell ######
###################
shellharden --replace ./**/*.sh .env.platforms
