#!//bin/bash
# run codex in a docker container and pass signals to it.
set -euxo pipefail
poetry install
_term() {
    echo "Caught SIGTERM signal!"
    kill -TERM "$child" # 2>/dev/null
}
trap _term SIGTERM

THIS_DIR="$(dirname "$0")"
cd "$THIS_DIR" || exit 1
export PYTHONPATH="${PYTHONPATH:-}:$THIS_DIR"
export DEBUG="${DEBUG:-1}"
export PYTHONDEVMODE="$DEBUG"  
export PYTHONDONTWRITEBYTECODE=1
kil % || true
./kill-codex.sh || true
poetry run python3 ./codex/run.py

child=$!
wait "$child"
sleep 10
