#!/bin/bash
# Lint checks
set -euxo pipefail

####################
###### Python ######
####################
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run vulture .
if [ "$(uname)" = "Darwin" ]; then
  # Radon is only of interest to development
  uv run radon mi --min B .
  uv run radon cc --min C .
fi
uv run djlint codex/templates --profile=django --lint

############################################
##### Javascript, JSON, Markdown, YAML #####
############################################
npm run lint

################################
###### Docker, Shell, Etc ######
################################
if [ "$(uname)" = "Darwin" ]; then
  # Hadolint & shfmt are difficult to install on linux
  # shellcheck disable=2035
  hadolint *Dockerfile
  shellharden ./**/*.sh
  # subdirs aren't copied into docker builder
  # .env files aren't copied into docker
  shellcheck --external-sources ./**/*.sh
  circleci config validate .circleci/config.yml
fi
./bin/roman.sh -i .prettierignore .
uv run codespell .
