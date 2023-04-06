.PHONY: install-backend-common
## Upgrade pip and poetry
install-backend-common:
	pip install --upgrade pip
	pip install --upgrade poetry
	npm install
	BREW_PREFIX=$(brew --prefix)
	export LDFLAGS="-L${BREW_PREFIX}/opt/openssl@3/lib"
	export CPPFLAGS="-I${BREW_PREFIX}/opt/openssl@3/include"
	export PKG_CONFIG_PATH="${BREW_PREFIX}/opt/openssl@3/lib/pkgconfig"

.PHONY: install-frontend
## Install frontend
install-frontend:
	bash -c "cd frontend && make install"

.PHONY: install
## Install for production
install: install-backend-common install-frontend
	poetry install --no-root --sync

.PHONY: install-dev
## Install dev requirements
install-dev: install-backend-common install-frontend
	poetry install  --no-root --extras=dev --sync

.PHONY: install-all
## Install all extras
install-all: install-backend-common install-frontend
	poetry install --no-root --all-extras --sync

.PHONY: clean
## Clean pycaches
clean:
	./bin/clean-pycache.sh

.PHONY: clean-frontend
## Clean static_build
clean-frontend:
	bash -c "cd frontend && make clean"

.PHONY: build-frontend
## Build frontend
build-frontend: clean-frontend
	bash -c "cd frontend && make build"

.PHONY: build
## Build python package
build:  build-frontend
	poetry build

.PHONY: publish
## Publish package to pypi
publish:
	./bin/pypi-deploy.sh

.PHONY: update
## Update dependencies
update:
	./bin/update-deps.sh

.PHONY: update-builder
## Update builder requirements
update-builder:
	./bin/update-builder-requirement.sh

.PHONY: fix-backend
## Fix only backend lint errors
fix-backend:
	./bin/fix-lint-backend.sh

.PHONY: fix-frontend
## Fix only frontend lint errors
fix-frontend:
	bash -c "cd frontend && make fix"

.PHONY: fix
## Fix front and back end lint errors
fix: fix-fronted fix-backend

.PHONY: lint-backend
## Lint the backend
lint-backend:
	./bin/lint-backend.sh

.PHONY: lint-frontend
## Lint the frontend
lint-frontend:
	bash -c "cd frontend && make lint"

.PHONY: lint
## Lint front and back end
lint: lint-frontend lint-backend

.PHONY: test-backend
## Run backend tests
test-backend:
	./bin/test-backend.sh

.PHONY: test-frontend
## Run frontend tests
test-frontend:
	./frontend/test.sh

.PHONY: test
## Run All Tests
test: test-frontend test-backend

.PHONY: dev-server
## Run the dev webserver
dev-server:
	./bin/dev-codex.sh

.PHONY: dev-frontend-server
## Run the vite dev frontend
dev-frontend-server:
	frontend/dev-server.sh

.PHONY: collectstatic
## Collect static files for django
collectstatic: build-frontend
	bin/collectstatic.sh

.PHONY: news
## Show recent NEWS
news:
	head -40 NEWS.md

.PHONY: icons
## Build all icons from source
icons:
	bin/create-icons.sh

.PHONY: benchmark-opds
## Time opds requests
benchmark-opds:
	bin/benchmark-opds.sh

.PHONY: kill
## Kill lingering codex processes
kill:
	kill %
	bin/kill-codex.sh

.PHONY: kill-eslint_d
## Kill eslint daemon
kill-eslint_d:
	bin/kill-eslint_d.sh

.PHONY: all

include bin/makefile-help.mk
