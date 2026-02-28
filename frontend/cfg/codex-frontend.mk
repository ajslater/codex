SHELL := /usr/bin/env bash
include ../cfg/help.mk

.PHONY: clean
## Remove static_build contents
## @category build
clean::
	rm -rf ../codex/static_build/*

.PHONY: dev-server
## Run Dev Frontend Server
## @category Run
dev-server:
	./bin/dev-server.sh

.PHONY: test
## Run All Tests
## @category Test
test:
	npm run test:ci

.PHONY: build
## Build package
## @category build
build: clean
	npm run build

.PHONY: all