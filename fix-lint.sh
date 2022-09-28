#!/bin/bash
set -euo pipefail
./sortignore.sh
./frontend/fix-lint.sh
./fix-lint-backend.sh
