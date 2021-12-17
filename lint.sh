#!/bin/bash
# Lint checks
set -euxo pipefail

####################
###### Python ######
####################
if [ "${1:-}" = "-f" ]; then
    # Fix as much as many linting issues as we can
    poetry run isort --color .
    poetry run black .
else
    poetry run isort --check-only .
    poetry run black --check .
fi
poetry run flake8 .
poetry run pyright
poetry run vulture .
if [ "$(uname)" = "Darwin" ]; then
    # Radon is only of interest to development
    poetry run radon mi --min B .
fi

########################
###### Javascript ######
########################
if [ "${1:-}" == "-f" ]; then
    bash -c "cd frontend && npx eslint --ext .js,.vue --fix '**'"
    prettier --write .
else
    bash -c "cd frontend && npx eslint --ext .js,.vue '**'"
    prettier --check .
fi

################################
###### Docker, Shell, Etc ######
################################
if [ "$(uname)" = "Darwin" ]; then
    # Hadolint & shfmt are difficult to install on linux
    # shellcheck disable=2035
    hadolint *.Dockerfile
    if [ "${1:-}" == "-f" ]; then
        shfmt -s -w -i 4 ./*.sh ./**/*.sh
    else
        shfmt -d -i 4 ./*.sh ./**/*.sh
    fi
fi
shellcheck -x ./*.sh ./**/*.sh
# shellcheck disable=2035
poetry run codespell *
