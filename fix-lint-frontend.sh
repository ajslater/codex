#!/bin/bash
# Fix lints frontend
set -euo pipefail
cd frontend
npm run lint
prettier --write .
