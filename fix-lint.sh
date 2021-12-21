#!/bin/bash
set -euxo pipefail
# Fix common linting errors
####################
###### Python ######
###################
poetry run isort --color .
poetry run black .

########################
###### Javascript ######
########################
bash -c "cd frontend && npx eslint --ext .js,.vue --fix '**'"
prettier --write .

###################
###### Shell ######
###################
shfmt -s -w -i 4 ./*.sh ./**/*.sh
