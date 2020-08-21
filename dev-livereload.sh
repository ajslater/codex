#!/bin/sh
# Run the django livereload app to trigger reloading the frontennd when the
#  api restarts
cd "$(dirname "$0")" || exit 1
DEV=1 ./pm livereload
