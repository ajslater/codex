#!/bin/bash
set -euxo pipefail
# DEBUG mode in django caches every query and so isn't good 
# for benchmarking memory intese query opterations
#export DEBUG=0
#export LOGLEVEL=DEBUG
VITE_HOST=localhost ./dev-codex.sh
