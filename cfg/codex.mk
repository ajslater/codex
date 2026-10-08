.PHONY: test-frontend
## Run frontend test with dependencies
## @category Test
test-frontend:: build-choices

.PHONY: lint
## Lint with dependencies: eslint resolves the generated choices JSON
## @category Lint
lint:: build-choices

.PHONY: fix
## Fix lint errors with dependencies: eslint resolves the generated choices JSON
## @category Fix
fix:: build-choices

.PHONY: dev
## Run Granian (backend) + Vite (frontend) together with interleaved logs
## @category Run Server
dev:
	./bin/dev.sh

.PHONY: dev-reverse-proxy
## Run a native nginx reverse proxy to codex with a url path prefix
## @category Run Server
dev-reverse-proxy:
	./bin/run-test-proxy.sh

## Module to run
## @category Run Server
M :=
.PHONY: dev-module
## Run a single codex module in dev mode
## @category Run Server
dev-module:
	./bin/dev-module.sh $(M)

.PHONY: build-choices
## Build JSON choices for frontend
## @category Build
build-choices:
	./bin/build-choices.sh

.PHONY: build
## Build codex dependencies
## @category Build
build:: build-choices

.PHONY: build-icons
## Build all icons from source
## @category Build Icons
build-icons:
	uv run --group build bin/icons_transform.py

.PHONY: sync-comic-logo
## Re-inline logo.svg into comic.svg as gray
## @category Build Icons
sync-comic-logo:
	uv run python bin/sync_comic_logo.py

.PHONY: perf-baseline
## Capture browser-views perf baseline via django-silk
## @category Test
perf-baseline:
	DEBUG=1 uv run --group lint python -m tests.perf.run_baseline