#!/usr/bin/env bash
# Fix Makefile, ignore file and shell script formatting
set -euxo pipefail

#####################
###### Makefile #####
#####################
uvx mbake@latest format Makefile cfg/*.mk

################
# Ignore files #
################
bin/sort-ignore.sh

###################
###### Shell ######
###################
bin/sh-tools.sh --fix
