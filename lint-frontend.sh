#!/bin/bash
set -euo pipefail
source circleci-build-skip.sh

cd "$(dirname "$(readlink "$0")")"/frontend
npm run lint
npx prettier --check .
