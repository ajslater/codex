SHELL := /usr/bin/env bash
DEVENV_SRC ?= ../devenv
DEVENV_COMMON := 1
export DEVENV_COMMON

.PHONY: clean
## Clean caches
## @category Clean
clean::
	rm -rf .*cache

## Flags for update-devenv, such as --no-update-deps
## @category Update
UPDATE_DEVENV_FLAGS :=
.PHONY: update-devenv
## Update development environment
## @category Update
update-devenv:
	uv run $(DEVENV_SRC)/scripts/update_devenv.py $(UPDATE_DEVENV_FLAGS)

.PHONY: fix
## Fix lint errors
## @category Fix
fix::
	./bin/fix.sh

.PHONY: fix-sh
## Fix shell script formatting
## @category Fix
fix-sh:
	./bin/sh-tools.sh --fix

.PHONY: lint
## Lint
## @category Lint
lint::
	./bin/lint.sh

.PHONY: lint-sh
## Lint shell scripts
## @category Lint
lint-sh:
	./bin/sh-tools.sh --lint

## Version to set. Leave empty to show the version
## @category Update
V :=

.PHONY: news
## Show recent NEWS
## @category Deploy
news:
	head -40 NEWS.md