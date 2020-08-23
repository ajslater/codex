#!/bin/sh
set -eu
PUID=${PUID:-911}
PGID=${PGID:-911}

groupmod --non-unique --gid "$PGID" abc
usermod --non-unique --uid "$PUID" abc

echo "
User uid:    $(id -u abc)
User gid:    $(id -g abc)
-------------------------------------
"
chown abc:abc /config
chown abc:abc /comics
