.PHONY: clean-frontend
## Clean frontend
## @category Clean
clean-frontend:
	cd frontend && make clean

.PHONY: clean
## Clean frontend too
## @category Clean
clean:: clean-frontend

.PHONY: install-frontend
## Install frontend
## @category Install
install-frontend:
	cd frontend && make install

.PHONY: install
## Install with all extras
## @category Install
install:: install-frontend

.PHONY: update-frontend
## Update deps for frontend
## @category Update
update-frontend:
	cd frontend && make update

.PHONY: update
## Update deps for frontend too
## @category Update
update:: update-frontend

.PHONY: fix-frontend
## Fix only frontend lint errors
## @category Lint
fix-frontend:
	bash -c "cd frontend && make fix"

.PHONY: fix
## Fix lint errors
## @category Lint
fix:: fix-frontend

.PHONY: lint-frontend
## Lint the frontend
## @category Lint
lint-frontend:
	bash -c "cd frontend && make lint"

.PHONY: lint-frontend
## Lint
## @category Lint
lint:: lint-frontend

.PHONY: dev-frontend-server
## Run the vite dev frontend
## @category Run
dev-frontend-server:
	bash -c "cd frontend && make dev-server"

.PHONY: test-frontend
## Run frontend tests
## @category Test
test-frontend::
	cd frontend && make test

.PHONY: test-frontend
## Run frontend tests too
## Test
## @category Test
test:: test-frontend

.PHONY: build-frontend
## Build frontend
## @category Build
build-frontend:
	cd frontend && make build

.PHONY: build
## Build with frontend
## @category Build
build:: build-frontend
