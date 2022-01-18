#!/bin/bash
set -euo pipefail
cd "$(dirname "$(readlink "$0")")"/frontend
npm run lint
prettier --check .
