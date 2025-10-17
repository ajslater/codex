export PATH=$PATH:"$HOME/.local/bin"
ENV_FN="$(./docker/docker-env-filename.sh)"
set -a
# shellcheck disable=SC1090
. "$ENV_FN"
set +a
