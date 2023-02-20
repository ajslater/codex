#!/bin/bash
# Run the django collectstatic command to collect static files from all
# locations specified in settings.STATIC_DIRS and place them in
# settings.STATIC_ROOT for production builds.
set -euo pipefail
BUILD=1 ./pm collectstatic --clear --no-input
