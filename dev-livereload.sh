#!/bin/sh
# Run the django livereload app to trigger reloading the frontennd when the
#  api restarts
cd "$(dirname "$0")" || exit 1
printf "Waiting for django server to start..."
until lsof -i -P -n | grep -q '9810.*LISTEN'; do
    sleep 1
    printf "."
done
printf '\n'
DEBUG=1 ./pm livereload
