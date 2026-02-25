.PHONY: docs
## Build doc site
## @category Docs
docs:
	uv run --only-group docs --no-dev mkdocs build --strict --site-dir docs/site

.PHONY: docs-server
## Run the docs server
## @category Docs
docs-server:
	uv run --only-group docs --no-dev mkdocs serve --open --dirty
