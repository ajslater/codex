ARG CODEX_WHEELS_VERSION
ARG CODEX_BASE_VERSION
FROM ajslater/codex-wheels:${CODEX_WHEELS_VERSION} as wheels
FROM ajslater/codex-base:${CODEX_BASE_VERSION} as base-installer
ARG CODEX_WHEEL
ENV CODEX_WHEELS=/wheels
WORKDIR /
COPY --from=wheels /cache/wheels/* /wheels/
COPY ./dist/$CODEX_WHEEL $CODEX_WHEELS/

RUN pip3 install --no-cache-dir --upgrade --find-links=$CODEX_WHEELS pip && \
  pip3 install --no-cache-dir --find-links=$CODEX_WHEELS $CODEX_WHEELS/$CODEX_WHEEL

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
