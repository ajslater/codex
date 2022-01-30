#!/bin/bash
# Fix lints frontend
set -euo pipefail
cd frontend
npm run fix
npx prettier --write .
