ARG CODEX_BUILDER_BASE_VERSION
ARG CODEX_BASE_VERSION
FROM ajslater/codex-builder-base:${CODEX_BUILDER_BASE_VERSION} AS codex-built
ARG CODEX_WHEEL
LABEL maintainer="AJ Slater <aj@slater.net>"
WORKDIR /app

# Install codex
COPY ./dist/$CODEX_WHEEL ./dist/$CODEX_WHEEL

# hadolint ignore=DL3059,DL3013
RUN PYMUPDF_SETUP_PY_LIMITED_API=0 pip3 install --no-cache-dir ./dist/$CODEX_WHEEL

FROM ajslater/codex-base:${CODEX_BASE_VERSION}
ARG PKG_VERSION
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=$PKG_VERSION

# Create the comics directory
RUN mkdir -p /comics && touch /comics/DOCKER_UNMOUNTED_VOLUME
# Fix Synology comicbox requiring config
RUN mkdir -p /home/abc/.config/comicbox \
  && chown -R abc /home/abc/.config \
  && chmod 777 /home/abc/.config /home/abc/.config/comicbox

# The final image is the mininimal base with /usr/local copied.
# Possibly could optimize this further to only get python and bin
COPY --from=codex-built /usr/local /usr/local

VOLUME /comics
VOLUME /config
EXPOSE 9810
CMD ["/usr/local/bin/codex"]
