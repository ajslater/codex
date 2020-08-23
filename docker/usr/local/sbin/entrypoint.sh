#!/bin/sh
set -eu
/usr/local/sbin/moduser.sh
su abc --shell /bin/sh --command "$@"
