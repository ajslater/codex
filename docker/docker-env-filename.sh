#
# Set the env filename var
ARCH=$(./docker/docker-arch.sh)
export ENV_FN=./.env-${ARCH}
