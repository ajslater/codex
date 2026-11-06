DEVENV_DOCS := 1
export DEVENV_DOCS

.PHONY: docs
## Build doc site
## @category Docs
docs:
	uv run --only-group docs --no-dev zensical build --strict

.PHONY: docs-server
## Run the docs server
## @category Docs
docs-server:
	uv run --only-group docs --no-dev zensical serve --open
