## Install for production
install:
	pip install --update pip
	poetry install --no-root

## Install dev requirements
install-dev:
	poetry install  --no-root --extras=dev

## Install all extras
install-all:
	poetry install --no-root --all-extras

## Build package
build:
	poetry build

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

## Show recent NEWS
news:
	head -40 NEWS.md

## Build all icons from source
icons:
	bin/create-icons.sh

.DEFAULT_GOAL := show-help
# See <https://gist.github.com/klmr/575726c7e05d8780505a> for explanation.
.PHONY: show-help
show-help:
	@echo "$$(tput bold)Available rules:$$(tput sgr0)";echo;sed -ne"/^## /{h;s/.*//;:d" -e"H;n;s/^## //;td" -e"s/:.*//;G;s/\\n## /---/;s/\\n/ /g;p;}" ${MAKEFILE_LIST}|LC_ALL='C' sort -f|awk -F --- -v n=$$(tput cols) -v i=19 -v a="$$(tput setaf 6)" -v z="$$(tput sgr0)" '{printf"%s%*s%s ",a,-i,$$1,z;m=split($$2,w," ");l=n-i;for(j=1;j<=m;j++){l-=length(w[j])+1;if(l<= 0){l=n-i-length(w[j])-1;printf"\n%*s ",-i," ";}printf"%s ",w[j];}printf"\n";}'|more $(shell test $(shell uname) == Darwin && echo '-Xr')
