ARG CODEX_BUILDER_FINAL_VERSION
ARG CODEX_WHEELS_VERSION
FROM ajslater/codex-builder-final:${CODEX_BUILDER_FINAL_VERSION} as codex-built
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=$CODEX_WHEELS_VERSION
WORKDIR /app
RUN ./python_cacher/link_wheels_from_caches.py copy
# hadolint ignore=DL3007
FROM tianon/true:latest
COPY --from=codex-built /app/cache/packages/wheels/* /wheels/
