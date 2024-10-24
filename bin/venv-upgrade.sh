#!/bin/bash
# Upgrade python venv
set -euxo pipefail

OLD_VERSION=$1
NEW_VERSION=$2
PYTHON_OLD="python$OLD_VERSION"
PYTHON_CMD="python$NEW_VERSION"
"$PYTHON_CMD" -m venv --upgrade .venv
rm -rf ".venv/lib/$PYTHON_OLD"
rm -f ".venv/bin/$PYTHON_OLD"
cd .venv/bin
ln -sf "$PYTHON_CMD" python3
ln -sf python3 python
PYOLD="py$OLD_VERSION"
PYNEW="py$NEW_VERSION"
find . -maxdepth 1 -type f -name 'activate*' -print0 | xargs -0 sed -i '' -e "s/$PYOLD/$PYNEW/g"
