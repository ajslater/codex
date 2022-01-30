#!/bin/bash
# Run all fixes and then all tests & lints.
# Good to do before commits
set -euo pipefail
./lint-frontend.sh
./test-frontend.sh
./build-frontend.sh
./test-backend.sh
./lint-backend.sh
