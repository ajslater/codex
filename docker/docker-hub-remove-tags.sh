#!/bin/bash
# Use docker hub API to login & delete tags
# Because docker/hub-tool won't do non-interactive login yet.
set -euo pipefail

ORGANIZATION="ajslater"
IMAGE="codex"
TAGS=("$@")

login_data() {
    cat <<EOF
{
  "username": "$DOCKER_USER",
  "password": "$DOCKER_PASS"
}
EOF
}

TOKEN=$(curl -s -H "Content-Type: application/json" -X POST -d "$(login_data)" "https://hub.docker.com/v2/users/login/" | jq -r .token)

URL_HEAD="https://hub.docker.com/v2/repositories/${ORGANIZATION}/${IMAGE}/tags"
for tag in "${TAGS[@]}"; do
    curl "$URL_HEAD/${tag}/" \
        -X DELETE \
        -H "Authorization: JWT ${TOKEN}"
done
