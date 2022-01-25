#!/bin/bash
# Lint checks
set -euxo pipefail
cd "$(dirname "$0")"
source circleci-build-skip.sh

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

############################################
##### Javascript, JSON, Markdown, YAML #####
############################################
npm run lint
npm run check

################################
###### Docker, Shell, Etc ######
################################
if [ "$(uname)" = "Darwin" ]; then
    # Hadolint & shfmt are difficult to install on linux
    # shellcheck disable=2035
    hadolint *.Dockerfile
    shfmt -d -i 4 ./*.sh ./**/*.sh
    # subdirs aren't copied into docker builder
    # .env files aren't copied into docker
    shellcheck --external-sources ./**/*.sh .env .env.platforms .env.pushover
    circleci config check .circleci/config.yml
fi
shellcheck --external-sources ./*.sh
poetry run codespell .
