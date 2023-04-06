#!/bin/bash
# Run front and back end tests
set -euo pipefail
./frontend/test.sh
./bin/test-backend.sh
