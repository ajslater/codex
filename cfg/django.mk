DEVENV_DJANGO := 1
export DEVENV_DJANGO

.PHONY: fix
## Fix django lint errors in templates
## @category Fix
fix::
	bin/fix-django.sh

.PHONY: lint
## Lint django templates
## @category Lint
lint::
	bin/lint-django.sh

.PHONY: django-check
## Django check
## @category Test
django-check:
	bin/pm check

.PHONY: collectstatic
## Collect static files for django
## @category Build
collectstatic: build-frontend
	bin/collectstatic.sh

.PHONY: build-only
## Build python package without collecting static files
## @category Build
build-only:
	uv build

.PHONY: build
## Collect static files before python.mk builds the package
## @category Build
build:: collectstatic