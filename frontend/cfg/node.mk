DEVENV_NODE := 1
export DEVENV_NODE

.PHONY: install-deps-node
## Update and install node packages
## @category Install
install-deps-node:
	bun install

.PHONY: install
## Install
## @category Install
install:: install-deps-node

.PHONY: update-node
## Update node dependencies
## @category Update
update-node:
	./bin/update-deps-node.sh

.PHONY: update
## Update dependencies
## @category Update
update:: update-node

.PHONY: kill-eslint_d
## Kill eslint daemon
## @category Lint
kill-eslint_d:
	bin/kill-eslint_d.sh

## Show version. Use V variable to set version
## @category Update
V :=
.PHONY: version
## Show or set project version for node
## @category Update
version::
	bin/version-node.sh $(V)