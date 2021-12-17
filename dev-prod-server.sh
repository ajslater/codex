#!/bin/bash
# run a production-like server
# XXX https://stackoverflow.com/questions/69394632/webpack-build-failing-with-err-ossl-evp-unsupported
THIS_DIR="$(dirname "$0")"
cd "$THIS_DIR" || exit 1
bash -c "cd frontend && npm run build"
./collectstatic.sh
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
export PYTHONPATH="$PYTHONPATH:$THIS_DIR"
poetry run python3 ./codex/run.py
