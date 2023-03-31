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
	poetry publish

## Update dependencies
update:
	./update-deps.sh

## Fix front and back end lint errors
fix:
	./fix-lint.sh

## Fix only backend lint errors
fix-backend:
	./fix-lint-backend.sh

## Fix only frontend lint errors
fix-frontend:
	./frontend/fix-lint.sh

## Lint front and back end
lint:
	./lint.sh

## Lint the backend
lint-backend:
	./lint-backend.sh

## Lint the frontend
lint-frontend:
	./frontend/lint.sh

## Run Tests
test:
	./test.sh

## Run the dev webserver
dev-server:
	./dev-codex.sh

## Run the vite dev frontend
dev-frontend:
	frontend/dev-server.sh

## Show recent NEWS
news:
	head -40 NEWS.md

.DEFAULT_GOAL := show-help
# See <https://gist.github.com/klmr/575726c7e05d8780505a> for explanation.
.PHONY: show-help
show-help:
	@echo "$$(tput bold)Available rules:$$(tput sgr0)";echo;sed -ne"/^## /{h;s/.*//;:d" -e"H;n;s/^## //;td" -e"s/:.*//;G;s/\\n## /---/;s/\\n/ /g;p;}" ${MAKEFILE_LIST}|LC_ALL='C' sort -f|awk -F --- -v n=$$(tput cols) -v i=19 -v a="$$(tput setaf 6)" -v z="$$(tput sgr0)" '{printf"%s%*s%s ",a,-i,$$1,z;m=split($$2,w," ");l=n-i;for(j=1;j<=m;j++){l-=length(w[j])+1;if(l<= 0){l=n-i-length(w[j])-1;printf"\n%*s ",-i," ";}printf"%s ",w[j];}printf"\n";}'|more $(shell test $(shell uname) == Darwin && echo '-Xr')
