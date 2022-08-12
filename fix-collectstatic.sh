#!/bin/bash
# This is necessary as of django 4.1 hopefully a fix is forthcoming from drf
set -euo pipefail
SP=$(poetry run pip show djangorestframework | rg Location | awk '{ print $2 }')
BASE_PATH="$SP/rest_framework/static/rest_framework/css"
touch "$BASE_PATH/bootstrap.min.css.map"
touch "$BASE_PATH/bootstrap-theme.min.css.map"
