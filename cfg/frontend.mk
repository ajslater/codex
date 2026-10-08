DEVENV_FRONTEND := 1
export DEVENV_FRONTEND

# Dummy target for mbake linting, which runs this file's first target with
# make -n. $(MAKE) lines run even under -n, and frontend/ may not exist there.
.PHONY: all
all:: ;

.PHONY: clean-frontend
## Clean frontend
## @category Clean
clean-frontend:
	$(MAKE) -C frontend clean

.PHONY: clean
## Clean frontend too
## @category Clean
clean:: clean-frontend

.PHONY: install-frontend
## Install frontend
## @category Install
install-frontend:
	$(MAKE) -C frontend install

.PHONY: install
## Install with all extras
## @category Install
install:: install-frontend

.PHONY: update-frontend
## Update deps for frontend
## @category Update
update-frontend:
	$(MAKE) -C frontend update

.PHONY: update
## Update deps for frontend too
## @category Update
update:: update-frontend

.PHONY: fix-frontend
## Fix only frontend lint errors
## @category Fix
fix-frontend:
	$(MAKE) -C frontend fix

.PHONY: fix
## Fix lint errors
## @category Fix
fix:: fix-frontend

.PHONY: lint-frontend
## Lint the frontend
## @category Lint
lint-frontend:
	$(MAKE) -C frontend lint

.PHONY: lint
## Lint
## @category Lint
lint:: lint-frontend

.PHONY: test-frontend
## Run frontend tests
## @category Test
test-frontend::
	$(MAKE) -C frontend test

.PHONY: test
## Run frontend tests too
## @category Test
test:: test-frontend

.PHONY: build-frontend
## Build frontend
## @category Build
build-frontend:
	$(MAKE) -C frontend build

.PHONY: build
## Build with frontend
## @category Build
build:: build-frontend