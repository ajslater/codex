ARG CODEX_BUILDER_FINAL_VERSION
ARG CODEX_BASE_VERSION
FROM ajslater/codex-builder-final:${CODEX_BUILDER_FINAL_VERSION} as codex-built
FROM ajslater/codex-base:${CODEX_BASE_VERSION}
ARG PKG_VERSION
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=$PKG_VERSION
# The final image is the mininimal base with /usr/local copied.
# Possibly could optimize this further to only get python and bin
COPY --from=codex-built /usr/local /usr/local

RUN mkdir -p /comics && touch /comics/DOCKER_UNMOUNTED_VOLUME

VOLUME /comics
VOLUME /config
EXPOSE 9810
CMD ["/usr/local/bin/codex"]
