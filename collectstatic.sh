#!/bin/bash
# Run the django collectstatic command to collect static files from all
# locations specified in settings.STATIC_DIRS and place them in
# settings.STATIC_ROOT for production builds.
set -euo pipefail
STATIC_PROD=$(poetry run python -c 'from codex.settings.settings import STATIC_ROOT; print(STATIC_ROOT)')
STATIC_CONFIG=$(poetry run python -c 'from codex.settings.settings import CONFIG_STATIC; print(CONFIG_STATIC)')
rm -rf "$STATIC_PROD"
mkdir -p "$STATIC_PROD" "$STATIC_CONFIG"
DEBUG=1 ./pm collectstatic --clear --ignore covers --no-input
