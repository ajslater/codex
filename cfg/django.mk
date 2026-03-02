.PHONY: fix
## Fix django lint errors in templates
## @category Fix
fix::
	uv run --group lint djlint --reformat **/templates/**/*.html

.PHONY: lint
## Lint django templates
## @category Lint
lint::
	uv run --group lint djlint --lint **/templates/**/*.html

.PHONY: dev-server
## Run the dev webserver
## @category Serve
dev-server:
	./bin/dev-server.sh

.PHONY: dev-prod-server
## Run a bundled production webserver
## @category Run Server
dev-prod-server: build-frontend collectstatic
	./bin/dev-prod-server.sh

.PHONY: collectstatic
## Collect static files for django
## @category Build
collectstatic: build-icons build-frontend
	bin/collectstatic.sh

.PHONY: django-check
## Django check
## @category Build
django-check:
	bin/pm check

.PHONY: build-only
## Build python package
## @category Build
build-only:
	uv build

.PHONY: build
## Build python package
## @category Build
build:: collectstatic build-only