#!/bin/bash
# Lint checks
set -euxo pipefail

####################
###### Python ######
####################
# Pytest runs these faster with caching
# poetry run isort --check-only .
# poetry run black --check .
# poetry run flake8 .
poetry run pyright
poetry run vulture .
if [ "$(uname)" = "Darwin" ]; then
    # Radon is only of interest to development
    poetry run radon mi --min B .
fi

########################
###### Javascript ######
########################
./lint-js.sh

################################
###### Docker, Shell, Etc ######
################################
if [ "$(uname)" = "Darwin" ]; then
    # Hadolint & shfmt are difficult to install on linux
    # shellcheck disable=2035
    hadolint *.Dockerfile
    shfmt -d -i 4 ./*.sh ./**/*.sh
fi
shellcheck -x ./*.sh ./**/*.sh
# shellcheck disable=2035
poetry run codespell .
