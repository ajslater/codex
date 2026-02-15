SHELL := /usr/bin/env bash

.PHONY: clean
## Clean caches
## @category Clean
clean::
	 rm -rf .*cache

.PHONY: install-deps-npm
## Update and install node packages
## @category Install
install-deps-npm:
	npm install

.PHONY: install
## Install
## @category Install
install:: install-deps-npm

.PHONY: update-npm
## Update npm dependencies
## @category Update
update-npm:
	./bin/update-deps-npm.sh || true

.PHONY: update
## Update dependencies
## @category Update
update:: update-npm

.PHONY: update-devenv
## Update development environment
## @category Update
update-devenv:
	bin/update-devenv.sh

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

.PHONY: kill-eslint_d
## Kill eslint daemon
## @category Lint
kill-eslint_d:
	bin/kill-eslint_d.sh

.PHONY: news
## Show recent NEWS
## @category Deploy
news:
	head -40 NEWS.md
