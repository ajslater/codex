#!/bin/bash
# Replace relative imports with direct vendor imports
set -euo pipefail
MODULE=$1
MODULE_DIR="codex/_vendor/$MODULE"
find "$MODULE_DIR" -name "*.py" -print0 | xargs -0 sed -ri '' "s/from \.+$MODULE/from codex._vendor.$MODULE/g"
