#!/bin/bash
# lint the front and back end
set -euo pipefail
./frontend/lint.sh
./lint-backend.sh
