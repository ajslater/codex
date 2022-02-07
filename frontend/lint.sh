#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"
npm run lint
npx prettier --check .
