.PHONY: install
## Configure wheel building for Darwin
## @category Install
install::
	BREW_PREFIX=$(brew --prefix)
	export LDFLAGS="-L${BREW_PREFIX}/opt/openssl@3/lib"
	export CPPFLAGS="-I${BREW_PREFIX}/opt/openssl@3/include"
	export PKG_CONFIG_PATH="${BREW_PREFIX}/opt/openssl@3/lib/pkgconfig"

.PHONY: test-frontend
## Run frontend test with dependencies
## @category Test
test-frontend:: build-choices

.PHONY: dev-ttabs
## Run the vite dev frontend and dev-server in ttabs
## @category Run Server
dev-ttabs:
	./bin/dev-ttabs.sh

.PHONY: dev-reverse-proxy
## Run an nginx reverse proxy to codex in docker
## @category Run Server
dev-reverse-proxy:
	./bin/dev-reverse-proxy.sh

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

.PHONY: build-icons
## Build all icons from source
## @category Build
build-icons:
	uv run --group build bin/icons_transform.py

.PHONY: build
## Build codex dependencies
## @category Build
build:: build-choices build-icons

.PHONY: perf-baseline
## Capture browser-views perf baseline via django-silk
## @category Test
perf-baseline:
	DEBUG=1 uv run --group lint python -m tests.perf.run_baseline