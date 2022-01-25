#!/bin/bash
set -euo pipefail
source circleci-build-skip.sh

cd "$(dirname "$0")"/frontend
npm run lint
npx prettier --check .
