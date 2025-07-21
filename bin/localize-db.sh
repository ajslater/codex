#!/bin/bash
# copy old database a localize
set -euo pipefail
REMOTE_DB=$1
LOCAL_LIB_PATH=$2
ROOT_PATH=$(realpath "$(dirname "$0")/..")
DB_PATH=$ROOT_PATH/config/codex.sqlite3
SQL_PATH=$(dirname "$0")/localize_library.sql
rm -f "$DB_PATH"-*
cp "$REMOTE_DB" "$DB_PATH"
SQL_DECLARE="DECLARE @LOCAL_LIB_PATH VARCHAR; SET @LOCAL_LIB_PATH = '$LOCAL_LIB_PATH';"
echo "$SQL_DECLARE" | cat - <("$SQL_PATH") | sqlite "$DB_PATH"
