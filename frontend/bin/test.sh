#!/bin/bash
# Run all frontend tests
set -euxo pipefail

cd "$(dirname "$0")"

npm run test:ci
