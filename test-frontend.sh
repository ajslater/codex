#!/bin/bash
# Run all frontend tests
set -euxo pipefail
source circleci-build-skip.sh

cd "$(dirname "$(readlink "$0")")"/frontend

npm run test:unit
