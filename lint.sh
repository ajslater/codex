#!/bin/bash
set -euo pipefail
./frontend/lint.sh
./lint-backend.sh
