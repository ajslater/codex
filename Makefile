SHELL := /usr/bin/env bash

.PHONY: activate
## Activate local virtual environment
## @category Env
activate:
	source .venv/bin/activate

.PHONY: update
## Update dependencies
## @category Update
update:
	./bin/update-deps.sh

.PHONY: update-builder
## Update builder requirements
## @category Update
update-builder:
	./bin/update-builder-requirement.sh

## version
## @category Update
V := 
.PHONY: version
## Show or set project version
## @category Update
version:
	bin/version.sh $(V)

.PHONY: install-backend-common
## Upgrade pip and poetry
## @category Install
install-backend-common:
	BREW_PREFIX=$(brew --prefix)
	export LDFLAGS="-L${BREW_PREFIX}/opt/openssl@3/lib"
	export CPPFLAGS="-I${BREW_PREFIX}/opt/openssl@3/include"
	export PKG_CONFIG_PATH="${BREW_PREFIX}/opt/openssl@3/lib/pkgconfig"
	pip install --upgrade pip
	pip install --upgrade poetry
	npm install

.PHONY: install-frontend
## Install frontend
## @category Install
install-frontend:
	bash -c "cd frontend && make install"

.PHONY: install
## Install for production
## @category Install
install: install-backend-common install-frontend
	poetry install --no-root --sync

.PHONY: install-dev
## Install dev requirements
## @category Install
install-dev: install-backend-common install-frontend
	poetry install  --no-root --extras=dev --sync

.PHONY: install-all
## Install all extras
## @category Install
install-all: install-backend-common install-frontend
	poetry install --no-root --all-extras --sync

.PHONY: fix-backend
## Fix only backend lint errors
## @category Fix
fix-backend:
	./bin/fix-lint-backend.sh

.PHONY: fix-frontend
## Fix only frontend lint errors
## @category Fix 
fix-frontend:
	bash -c "cd frontend && make fix"

.PHONY: fix
## Fix front and back end lint errors
## @category Fix
fix: fix-frontend fix-backend

.PHONY: lint-backend
## Lint the backend
## @category Lint
lint-backend:
	./bin/lint-backend.sh

.PHONY: lint-frontend
## Lint the frontend
## @category Lint
lint-frontend:
	bash -c "cd frontend && make lint"

.PHONY: lint
## Lint front and back end
## @category Lint
lint: lint-frontend lint-backend

.PHONY: check
## Check django is ok
## @category Lint
check:
	./bin/pm check

.PHONY: typecheck 
## Static typecheck
## @category Lint
typecheck:
	poetry run pyright .


.PHONY: test-backend
## Run backend tests
## @category Test
test-backend:
	./bin/test-backend.sh

.PHONY: test-frontend
## Run frontend tests
## @category Test
test-frontend:
	bash -c "cd frontend && make test"

.PHONY: test
## Run All Tests
## @category Test
test: test-frontend test-backend

.PHONY: benchmark-opds
## Time opds requests
## @category Test
benchmark-opds:
	bin/benchmark-opds.sh

.PHONY: clean
## Clean pycaches
## @category Build
clean:
	./bin/clean-pycache.sh

.PHONY: clean-frontend
## Clean static_build
## @category Build
clean-frontend:
	bash -c "cd frontend && make clean"

.PHONY: build-frontend
## Build frontend
## @category Build
build-frontend: clean-frontend
	bash -c "cd frontend && make build"

.PHONY: icons
## Build all icons from source
## @category Build
icons:
	bin/icons_transform.py

.PHONY: collectstatic
## Collect static files for django
## @category Build
collectstatic:
	bin/collectstatic.sh

.PHONY: build-backend
## Build python package
## @category Build
build-backend: collectstatic check
	poetry build

.PHONY: build
## Build python package
## @category Build
build: build-frontend build-backend

.PHONY: choices
## Build JSON choices for frontend
## @category Build
choices:
	./bin/build-choices.sh

.PHONY: kill
## Kill lingering codex processes
## @category Run Server
kill:
	bin/kill-codex.sh || true

.PHONY: dev-server
## Run the dev webserver
## @category Run Server
dev-server: kill 
	./bin/dev-server.sh

.PHONY: dev-prod-server
## Run a bundled production webserver
## @category Run Server
dev-prod-server: build-frontend collectstatic
	./bin/dev-prod-server.sh

.PHONY: dev-frontend-server
## Run the vite dev frontend
## @category Run Server
dev-frontend-server:
	frontend/dev-server.sh

.PHONY: dev-ttabs
## Run the vite dev frontend and dev-server in ttabs
## @category Run Server
dev-ttabs:
	./bin/dev-ttabs.sh

.PHONY: dev-reverse-proxy
## Run an nginx reverse proxy to codex in docker
## @category Run Server
dev-reverse-proxy:
	./bin/dev-reverse-proxy.sh

.PHONY: dev-docker
## Restart codex in docker
## @category Run Server
dev-docker:
	./bin/dev-docker.sh

## Module to run
## @category Run Server
M := 
.PHONY: dev-module
## Run a single codex module in dev mode
## @category Run Server
dev-module:
	./bin/dev-module.sh $(M)

.PHONY: publish
## Publish package to pypi
## @category Deploy
publish:
	./bin/pypi-deploy.sh

.PHONY: news
## Show recent NEWS
## @category Deploy
news:
	head -40 NEWS.md

.PHONE: uml
## Create uml diagrams
## @category Dev
uml:
	./bin/uml.sh

.PHONY: all


include bin/makefile-help.mk
