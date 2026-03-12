DEVENV_DOCKER := 1
export DEVENV_DOCKER

.PHONY: fix
## Fix docker lint errors
## @category Fix
fix::
	bin/fix-docker.sh

.PHONY: lint
## Lint docker files
## @category Lint
lint::
	bin/lint-docker.sh