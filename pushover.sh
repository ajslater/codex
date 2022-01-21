#!/bin/bash
set -euo pipefail
cd "$(dirname "$(readlink "$0")")"
# shellcheck source=/dev/null
source .env.pushover
export PUSHOVER_API_TOKEN
export PUSHOVER_USER_ID
poetry run pushover -s$? "$1"
