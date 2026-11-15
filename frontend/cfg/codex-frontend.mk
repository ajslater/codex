SHELL := /usr/bin/env bash

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

# The root lint and fix skip frontend/ (devenv's frontend feature passes eslint
# --ignore-pattern frontend/), and this Makefile has no node_root feature, so
# these are the only eslint and prettier runs over the frontend.
.PHONY: fix
## Fix JS, Vue, JSON, CSS and Markdown with eslint and prettier
## @category Fix
fix::
	bun run fix

.PHONY: lint
## Lint JS, Vue, JSON, CSS and Markdown with eslint and prettier
## @category Lint
lint::
	bun run lint

.PHONY: test
## Run All Tests
## @category Test
test:
	bun run test:ci

.PHONY: build
## Build package
## @category build
build: clean
	bun run build

.PHONY: all
