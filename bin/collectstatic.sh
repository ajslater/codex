#!/usr/bin/env bash
# Run django's collectstatic to gather static files from settings.STATICFILES_DIRS
# into settings.STATIC_ROOT for production builds -- when there are any.
#
# Chronicle's django side is a telemetry receiver with no templates and no
# static files of its own, so django.contrib.staticfiles is not installed and
# `collectstatic` is not a registered command: calling it is a hard error, not
# a no-op. The dashboard's frontend is built by vite and served by fastapi out
# of its own dist directory, which django never sees.
#
# `make build` runs this, and a build should not fail over a step that does not
# apply to it. So ask django what it has before asking it to collect, and say
# why when the answer is nothing.
set -euo pipefail
IGNORE="rest_framework"

# Asked of django rather than of the settings file, so a settings module that
# grows staticfiles later turns this on without anyone editing the script.
# --verbosity 0: django's shell announces how many models it auto-imported,
# on stdout, which would otherwise be most of the answer read back here.
VERDICT="$(BUILD=1 COLLECTSTATIC_IGNORE="$IGNORE" ./bin/pm shell --verbosity 0 --command "
import os

from django.apps import apps
from django.conf import settings

if not apps.is_installed('django.contrib.staticfiles'):
    print('no-app')
elif not settings.STATIC_ROOT:
    print('no-root')
else:
    from django.contrib.staticfiles.finders import get_finders

    ignore = [os.environ['COLLECTSTATIC_IGNORE']]
    found = any(True for finder in get_finders() for _ in finder.list(ignore))
    print('collect' if found else 'no-files')
")"

case "$VERDICT" in
collect)
  BUILD=1 ./bin/pm collectstatic --clear --no-input --ignore "$IGNORE"
  ;;
no-app)
  echo "django.contrib.staticfiles is not installed. Nothing to collect."
  ;;
no-root)
  echo "settings.STATIC_ROOT is unset. Nothing to collect."
  ;;
no-files)
  echo "No static files found outside $IGNORE. Nothing to collect."
  ;;
*)
  echo "Could not tell whether to collect static files. django said:" >&2
  echo "$VERDICT" >&2
  exit 1
  ;;
esac
