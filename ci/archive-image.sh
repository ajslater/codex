#!/bin/bash
set -euo pipefail
source ./env
docker save -o "$1" "$IMAGE"
