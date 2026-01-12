SHELL := /usr/bin/env bash

## Show version. Use V variable to set version
## @category Update
V :=
.PHONY: version
## Show or set project version
## @category Update
version:
	bin/version.sh $(V)

.PHONY: install-deps
## Update pip and install node packages
## @category Install
install-deps:
	BREW_PREFIX=$(brew --prefix)
	export LDFLAGS="-L${BREW_PREFIX}/opt/openssl@3/lib"
	export CPPFLAGS="-I${BREW_PREFIX}/opt/openssl@3/include"
	export PKG_CONFIG_PATH="${BREW_PREFIX}/opt/openssl@3/lib/pkgconfig"
	pip install --upgrade pip
	npm install

.PHONY: install-frontend
## Install frontend
## @category Install
install-frontend:
	cd frontend && make install

.PHONY: install-dev
## Install dev requirements
## @category Install
install-dev: install-deps install-frontend
	uv sync --no-install-project

.PHONY: install
## Install for production
## @category Install
install-prod: install-deps
	uv sync --no-install-project --no-dev

.PHONY: install-all
## Install with all extras
## @category Install
install-all: install-deps install-frontend
	uv sync --no-install-project --all-extras

.PHONY: clean
## Clean pycaches
## @category Build
clean:
	./bin/clean-pycache.sh

.PHONY: clean-frontend
## Clean static_build
## @category Build
clean-frontend:
	cd frontend && make clean

.PHONY: build-choices
## Build JSON choices for frontend
## @category Build
build-choices:
	./bin/build-choices.sh

.PHONY: build-frontend
## Build frontend
## @category Build
build-frontend: build-choices
	cd frontend && make build

.PHONY: build-icons
## Build all icons from source
## @category Build
build-icons:
	uv run --group build bin/icons_transform.py

.PHONY: collectstatic
## Collect static files for django
## @category Build
collectstatic: build-icons build-frontend
	bin/collectstatic.sh

.PHONE: django-check
## Django check
## @category Build
django-check:
	bin/pm check

.PHONY: build-backend
## Build python package
## @category Build
build-backend: collectstatic
	uv build

.PHONY: build
## Build python package
## @category Build
build: build-backend

.PHONY: publish
## Publish package to pypi
## @category Deploy
publish:
	uv publish

.PHONY: update
## Update dependencies
## @category Update
update:
	./bin/update-deps.sh

.PHONY: kill-eslint_d
## Kill eslint daemon
## @category Lint
kill-eslint_d:
	bin/kill-eslint_d.sh

.PHONY: fix-frontend
## Fix only frontend lint errors
## @category Fix 
fix-frontend:
	cd frontend && make fix

.PHONY: fix-backend
## Fix only backend lint errors
## @category Fix
fix-backend:
	./bin/fix-lint-backend.sh

.PHONY: fix
## Fix front and back end lint errors
## @category Fix
fix: fix-backend fix-frontend

.PHONY: typecheck
## Static typecheck
## @category Lint
typecheck:
	uv run --group lint --no-dev basedpyright .

.PHONY: ty
## Static typecheck with ty
## @category Lint
ty:
	uv run --group lint --no-dev ty check .

.PHONY: lint-frontend
## Lint the frontend
## @category Lint
lint-frontend:
	cd frontend && make lint

.PHONY: lint-backend
## Lint the backend
## @category Lint
lint-backend:
	./bin/lint-backend.sh

.PHONY: complexity
## Lint backend complexity
## @category Lint
complexity:
	./bin/lint-backend-complexity.sh

.PHONY: lint
## Lint front and back end
## @category Lint
lint: lint-backend lint-frontend

.PHONY: uml
## Create a UML class diagram
## #category Lint
uml:
	bin/uml.sh

.PHONY: cycle
## Detect Circular imports
## @category Lint
cycle:
	uvx pycycle --ignore node_modules,.venv --verbose --here

.PHONY: test-frontend
## Run frontend tests
## Test
 ## @category Test
test-frontend: build-choices
	cd frontend && make test

.PHONY: test-backend
## Run backend tests. Use T variable to run specific tests
## @category Test
T := 
test-backend: collectstatic django-check
	./bin/test-backend.sh $(T)

.PHONY: test
## Run Tests.
## @category Test
test: test-frontend test-backend

.PHONY: benchmark-opds
## Time opds requests
## @category Test
benchmark-opds:
	bin/benchmark-opds.sh

.PHONY: dev-frontend-server
## Run the vite dev frontend
## @category Run Server
dev-frontend-server:
	cd frontend && make dev-server

.PHONY: dev-server
## Run the dev webserver
## @category Test
dev-server:
	./bin/dev-server.sh

.PHONY: dev-prod-server
## Run a bundled production webserver
## @category Run Server
dev-prod-server: build-frontend collectstatic
	./bin/dev-prod-server.sh

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

.PHONY: kill
## Kill lingering codex processes
## @category Run Server
kill:
	bin/kill-codex.sh || true

.PHONY: news
## Show recent NEWS
## @category Deploy
news:
	head -40 NEWS.md

.PHONY: docs
## Build doc site
## @category Docs
docs:
	uv run --only-group docs --no-dev mkdocs build --strict --site-dir docs/site

.PHONY: docs-server
## Build doc site
## @category Docs
docs-server:
	uv run --only-group docs mkdocs serve --open --dirty


.PHONY: all

include bin/makefile-help.mk
