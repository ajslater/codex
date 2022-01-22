#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
# shellcheck disable=SC1091
source .env.pushover
export PUSHOVER_API_TOKEN
export PUSHOVER_USER_ID
poetry run pushover -s$? "$1"
