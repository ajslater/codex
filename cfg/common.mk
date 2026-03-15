SHELL := /usr/bin/env bash
DEVENV_SRC ?= ../devenv
# export DEVENV_SRC
DEVENV_COMMON := 1
export DEVENV_COMMON

.PHONY: clean
## Clean caches
## @category Clean
clean::
	 rm -rf .*cache

.PHONY: update-devenv
## Update development environment
## @category Update
update-devenv:
	$(DEVENV_SRC)/scripts/update-devenv.sh

.PHONY: fix
## Fix lint errors
## @category Fix
fix::
	./bin/fix.sh

.PHONY: lint
## Lint
## @category Lint
lint::
	./bin/lint.sh

.PHONY: news
## Show recent NEWS
## @category Deploy
news:
	head -40 NEWS.md