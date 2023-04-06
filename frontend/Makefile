## Upgrade pip and poetry
install:
	npm install

## Build package
build: clean
	npm run build

## Remove static_build contents
clean:
.PHONY: clean
	rm -rf ../codex/static_build/*

## Fix only frontend lint errors
fix:
	./bin/fix-lint.sh

## Lint front and back end
lint:
	./bin/lint.sh

## Run All Tests
test:
.PHONY: test
	./bin/test.sh

include ../bin/makefile-help.mk
