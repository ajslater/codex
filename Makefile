## Upgrade pip and poetry
install-backend-common:
	pip install --upgrade pip
	pip install --upgrade poetry
	npm install
	BREW_PREFIX=$(brew --prefix)
	export LDFLAGS="-L${BREW_PREFIX}/opt/openssl@3/lib"
	export CPPFLAGS="-I${BREW_PREFIX}/opt/openssl@3/include"
	export PKG_CONFIG_PATH="${BREW_PREFIX}/opt/openssl@3/lib/pkgconfig"


## Install frontend
install-frontend:
	bash -c "cd frontend && npm install"

## Install for production
install: install-backend-common install-frontend
	poetry install --no-root --sync

## Install dev requirements
install-dev: install-backend-common install-frontend
	poetry install  --no-root --extras=dev --sync

## Install all extras
install-all: install-backend-common install-frontend
	poetry install --no-root --all-extras --sync

## Build package
build:
	poetry build

## Build frontend
build-frontend:
	bash -c "cd frontend && npm run build"

## Publish package to pypi
publish:
	./bin/pypi-deploy.sh

## Update dependencies
update:
	./bin/update-deps.sh

## Update builder requirements
update-builder:
	./bin/update-builder-requirement.sh

## Fix front and back end lint errors
fix:
	./bin/fix-lint.sh

## Fix only backend lint errors
fix-backend:
	./bin/fix-lint-backend.sh

## Fix only frontend lint errors
fix-frontend:
	./frontend/fix-lint.sh

## Lint front and back end
lint:
	./bin/lint.sh

## Lint the backend
lint-backend:
	./bin/lint-backend.sh

## Lint the frontend
lint-frontend:
	./frontend/lint.sh

## Clean pycaches
clean:
.PHONY: clean
	./bin/clean-pycache.sh

## Run All Tests
test:
.PHONY: test
	./bin/test.sh

## Run backend tests
test-backend:
	./bin/test-backend.sh

## Run frontend tests
test-frontend:
	./frontend/test.sh

## Run the dev webserver
dev-server:
	./dev-codex.sh

## Run the vite dev frontend
dev-frontend:
	frontend/dev-server.sh

## Collect static files for django
collectstatic: build-frontend
	bin/collectstatic.sh

## Show recent NEWS
news:
	head -40 NEWS.md

## Build all icons from source
icons:
	bin/create-icons.sh

## Time opds requests
benchmark-opds:
	bin/benchmark-opds.sh

## Kill lingering codex processes
kill:
	kill %
	bin/kill-codex.sh

## Kill eslint daemon
kill-eslint_d:
	bin/kill-eslint_d.sh

.DEFAULT_GOAL := show-help
# See <https://gist.github.com/klmr/575726c7e05d8780505a> for explanation.
.PHONY: show-help
show-help:
	@echo "$$(tput bold)Available rules:$$(tput sgr0)";echo;sed -ne"/^## /{h;s/.*//;:d" -e"H;n;s/^## //;td" -e"s/:.*//;G;s/\\n## /---/;s/\\n/ /g;p;}" ${MAKEFILE_LIST}|LC_ALL='C' sort -f|awk -F --- -v n=$$(tput cols) -v i=19 -v a="$$(tput setaf 6)" -v z="$$(tput sgr0)" '{printf"%s%*s%s ",a,-i,$$1,z;m=split($$2,w," ");l=n-i;for(j=1;j<=m;j++){l-=length(w[j])+1;if(l<= 0){l=n-i-length(w[j])-1;printf"\n%*s ",-i," ";}printf"%s ",w[j];}printf"\n";}'|more $(shell test $(shell uname) == Darwin && echo '-Xr')
