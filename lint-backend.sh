#!/bin/bash
# Lint checks
set -euxo pipefail
cd "$(dirname "$(readlink "$0")")"

####################
###### Python ######
####################
# Pytest runs flake8, black, isort faster with caching
poetry run pyright
poetry run vulture .
if [ "$(uname)" = "Darwin" ]; then
    # Radon is only of interest to development
    poetry run radon mi --min B .
fi

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
