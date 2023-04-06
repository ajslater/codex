#!/bin/bash
# fix front and backend lints.
set -euo pipefail
./bin/sortignore.sh
./frontend/fix-lint.sh
./bin/fix-lint-backend.sh
