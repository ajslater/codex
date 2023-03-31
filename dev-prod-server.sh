#!/bin/bash
# run a production-like server
THIS_DIR="$(dirname "$0")"
cd "$THIS_DIR" || exit 1
if [ "${BUILD:-1}" = 1 ]; then
    bash -c "cd frontend && npm run build"
    ./collectstatic.sh
fi
export PYTHONPATH="$PYTHONPATH:$THIS_DIR"
poetry run python3 ./codex/run.py
