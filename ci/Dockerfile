ARG CODEX_BUILDER_BASE_VERSION
ARG CODEX_BASE_VERSION
FROM ajslater/codex-builder-base:${CODEX_BUILDER_BASE_VERSION} AS codex-built
ARG CODEX_WHEEL
WORKDIR /app

# Install codex
COPY ./dist/$CODEX_WHEEL ./dist/$CODEX_WHEEL

# hadolint ignore=DL3059,DL3013
RUN PYMUPDF_SETUP_PY_LIMITED_API=0 pip3 install --no-cache-dir ./dist/$CODEX_WHEEL

# Slim down /usr/local before it gets copied to the final image
# hadolint ignore=DL3059
RUN set -eux \
    # Remove pip, setuptools, wheel — not needed at runtime
    && pip3 uninstall -y pip setuptools wheel 2>/dev/null || true \
    && rm -rf /usr/local/bin/pip* \
    # Strip debug symbols from shared libraries (~30-50% size reduction on .so files)
    && find /usr/local -name '*.so' -exec strip --strip-unneeded {} + 2>/dev/null || true \
    && find /usr/local -name '*.so.*' -exec strip --strip-unneeded {} + 2>/dev/null || true \
    # Remove Python bytecode caches (regenerated on first import)
    && find /usr/local -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local -name '*.pyc' -delete 2>/dev/null || true \
    # Remove the stdlib test suite (~30MB) — safe, never needed at runtime
    && rm -rf /usr/local/lib/python*/test \
    && rm -rf /usr/local/lib/python*/idlelib \
    && rm -rf /usr/local/lib/python*/ensurepip \
    # Remove type stubs — only used by type checkers
    && find /usr/local -name '*.pyi' -delete 2>/dev/null || true \
    # Remove the installed wheel
    && rm -f /tmp/${CODEX_WHEEL}

FROM ajslater/codex-base:${CODEX_BASE_VERSION}
ARG CODEX_VERSION
LABEL org.opencontainers.image.title="Codex" \
    org.opencontainers.image.version="${CODEX_VERSION}" \
    org.opencontainers.image.authors="AJ Slater <aj@slater.net>" \
    org.opencontainers.image.url="https://codex-reader-app" \
    org.opencontainers.image.source="https://github.com/ajslater/codex" \
    org.opencontainers.image.licenses="GPL-3.0-only" \
    org.opencontainers.image.deprecated="true" \
    org.opencontainers.image.description="This image has moved to ghcr.io/ajslater/codex"
ENV DOCKER_IMAGE_DEPRECATED="This docker image has moved to ghcr.io/ajslater/codex. This may be the last version on docker.io"

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
