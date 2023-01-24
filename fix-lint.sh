#!/bin/bash
# fix front and backend lints.
set -euo pipefail
./sortignore.sh
./frontend/fix-lint.sh
./fix-lint-backend.sh
