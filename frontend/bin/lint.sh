#!/bin/bash
# lint the frontend
set -euo pipefail

npm run lint
npx prettier --check .
