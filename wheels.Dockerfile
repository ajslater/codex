ARG CODEX_DIST_BUILDER_VERSION
FROM ajslater/codex-dist-builder:$CODEX_DIST_BUILDER_VERSION as wheels-builder
# build binary wheels in a dev environment for each arch

WORKDIR /app
COPY ./harvest_wheels.py /app/
RUN ./harvest_wheels.py /cache

# hadolint ignore=DL3007
FROM tianon/true:latest
ARG CODEX_WHEELS_VERSION
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version $CODEX_WHEELS_VERSION

COPY --from=wheels-builder /cache /cache
