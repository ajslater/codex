export PATH=$PATH:"$HOME/.local/bin"
export DOCKER_CLI_EXPERIMENTAL=enabled
export DOCKER_BUILDKIT=1
ENV_FN="$(./docker/docker-env-filename.sh)"
set -a
# shellcheck disable=SC1090
. "$ENV_FN"
set +a
