DEVENV_CI := 1
export DEVENV_CI

.PHONY: lint
## Lint ci errors
## @category Lint
lint::
	bin/lint-ci.sh