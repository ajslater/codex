DEVENV_NODE_ROOT := 1
export DEVENV_NODE_ROOT

.PHONY: fix
## Fix JS, JSON, Markdown, TOML and YAML with eslint and prettier
## @category Fix
fix::
	bun run fix

.PHONY: lint
## Lint JS, JSON, Markdown, TOML and YAML with eslint and prettier
## @category Lint
lint::
	bun run lint
