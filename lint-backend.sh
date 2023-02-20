#!/bin/bash
# Lint checks
set -euxo pipefail
cd "$(dirname "$0")"

####################
###### Python ######
####################
poetry run ruff .
poetry run black --check .
poetry run pyright
poetry run vulture .
if [ "$(uname)" = "Darwin" ]; then
    # Radon is only of interest to development
    poetry run radon mi --min B .
    poetry run radon cc --min C .
fi
poetry run djlint codex/templates --profile=django --lint

############################################
##### Javascript, JSON, Markdown, YAML #####
############################################
npm run lint
npm run remark-check

################################
###### Docker, Shell, Etc ######
################################
if [ "$(uname)" = "Darwin" ]; then
    # Hadolint & shfmt are difficult to install on linux
    # shellcheck disable=2035
    hadolint *Dockerfile
    shellharden ./*.sh ./**/*.sh
    # subdirs aren't copied into docker builder
    # .env files aren't copied into docker
    shellcheck --external-sources ./**/*.sh .env.platforms
    circleci config check .circleci/config.yml
fi
shellcheck --external-sources ./*.sh
poetry run codespell .
