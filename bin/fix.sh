#!/usr/bin/env bash
# Fix common linting errors
set -euxo pipefail

#####################
###### Makefile #####
#####################
uv run mbake format Makefile

################
# Ignore files #
################
bin/sort-ignore.sh

############################################
##### Javascript, JSON, Markdown, YAML #####
############################################
npm run fix

###################
###### Shell ######
###################
shellharden --replace ./**/*.sh
