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
# node_root merges a fix script; a project without node_root may have none.
bun run --if-present fix

###################
###### Shell ######
###################
bin/sh-tools.sh --fix
