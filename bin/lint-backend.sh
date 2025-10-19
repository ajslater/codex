#!/bin/bash
# Lint checks
set -euxo pipefail

export UV_NO_DEV=1
####################
###### Python ######
####################
uv run --group lint ruff check .
uv run --group lint ruff format --check .
uv run --group build --group lint --group ci test basedpyright
uv run --group lint vulture .
if [ "$(uname)" = "Darwin" ]; then
  # Radon is only of interest to development
  uv run --group lint radon mi --min B .
  uv run --group lint radon cc --min C .
fi
uv run --group lint djlint codex/templates/*.html codex/templates/pwa/*.html --lint

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
  hadolint ci/*Dockerfile
  shellharden --check ./**/*.sh .env.platforms
  # subdirs aren't copied into docker builder
  # .env files aren't copied into docker
  shellcheck --external-sources ./**/*.sh
  circleci config validate .circleci/config.yml
fi
./bin/roman.sh -i .prettierignore .
uv run --group lint codespell .
