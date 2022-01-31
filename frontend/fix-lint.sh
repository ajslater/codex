#!/bin/bash
# Fix lints frontend
set -euo pipefail
cd "$(dirname "$0")"
npm run fix
npx prettier --write .
