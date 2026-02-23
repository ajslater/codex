SHELL := /usr/bin/env bash
include cfg/help.mk
include cfg/codex.mk
include cfg/django.mk
include cfg/docs.mk
include cfg/python.mk
include cfg/common.mk
include cfg/frontend.mk

.PHONY: all