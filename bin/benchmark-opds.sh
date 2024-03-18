#!/bin/bash
# benchmark opds url times
set -euo pipefail

BASE_URL="http://localhost:9810"
OPDS_BASE="/opds/v1.2"

timeit() {
  echo "${1}":
  TEST_PATH="${OPDS_BASE}${2}"
  echo -e "\t$TEST_PATH"
  URL="${BASE_URL}${TEST_PATH}"
  /usr/bin/time -h curl -S -s -o /dev/null "$URL"
}

timeit "Recently Added:" "/s/0/1?orderBy=created_at&orderReverse=True"
#timeit "All Series" "/r/0/1?topGroup=s"
