#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"/frontend
npm run lint
npx prettier --check .
