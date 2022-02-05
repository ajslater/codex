#!/bin/bash
set -euo pipefail
./frontend/fix-lint.sh
./fix-lint-backend.sh
