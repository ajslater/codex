#!/bin/bash
# Lint checks
set -euxo pipefail
cd "$(dirname "$0")"

####################
###### Python ######
####################
poetry run flake8 .
poetry run black --check .
poetry run isort --check-only .
poetry run pyright
poetry run bandit -r -c "pyproject.toml" --confidence-level=medium --severity-level=medium codex
poetry run vulture .
poetry run eradicate .
if [ "$(uname)" = "Darwin" ]; then
    # Radon is only of interest to development
    poetry run radon mi --min B .
fi
poetry run djlint codex/templates --profile=django --lint

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
    #shfmt -d -i 4 ./*.sh ./**/*.sh
    shellharden ./*.sh ./**/*.sh
    # subdirs aren't copied into docker builder
    # .env files aren't copied into docker
    shellcheck --external-sources ./**/*.sh .env.platforms .env.pushover
    circleci config check .circleci/config.yml
fi
shellcheck --external-sources ./*.sh
poetry run codespell .
