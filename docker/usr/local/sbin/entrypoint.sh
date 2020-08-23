#!/bin/sh
set -eu
if [ -n "${PUID:-}${PGID:-}"  ]; then
    /usr/local/sbin/moduser.sh
    su abc --shell /bin/sh --command "$@"
else
    exec "$@"
fi
