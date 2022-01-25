ARG CODEX_BASE_VERSION
FROM ajslater/codex-base:${CODEX_BASE_VERSION} as base-installer
ARG HOST_CACHE_DIR
ARG CODEX_WHEEL
ENV WHEELS=./cache/packages/wheels
WORKDIR /
# Copy in caches and codex wheel
COPY $HOST_CACHE_DIR/pip /root/.cache/pip
COPY $HOST_CACHE_DIR/pypoetry /root/.cache/pypoetry
COPY ./link_wheels_from_caches.py .
RUN ./link_wheels_from_caches.py
COPY ./dist/$CODEX_WHEEL $WHEELS/$CODEX_WHEEL

# Install codex
RUN pip3 install --no-cache-dir --upgrade --find-links=$WHEELS pip
# hadolint ignore=DL3059
RUN pip3 install --no-cache-dir --find-links=$WHEELS $WHEELS/$CODEX_WHEEL

FROM ajslater/codex-base:${CODEX_BASE_VERSION}
ARG PKG_VERSION
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=$PKG_VERSION
# The final image is the mininimal base with /usr/local copied.
COPY --from=base-installer /usr/local /usr/local

RUN mkdir -p /comics && touch /comics/DOCKER_UNMOUNTED_VOLUME

VOLUME /comics
VOLUME /config
EXPOSE 9810
CMD ["/usr/local/bin/codex"]
