#!/usr/bin/env bash
# Fix common linting errors
set -euxo pipefail

#####################
###### Makefile #####
#####################
uvx mbake@latest format Makefile cfg/*.mk

################
# Ignore files #
################
bin/sort-ignore.sh

############################################
##### Javascript, JSON, Markdown, YAML #####
############################################
bun run fix

###################
###### Shell ######
###################
bin/sh-tools.sh --fix
