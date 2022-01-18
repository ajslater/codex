ARG WHEELS_VERSION
ARG RUNNABLE_BASE_VERSION
FROM ajslater/codex-wheels:$WHEELS_VERSION AS codex-wheels
# The runnable environment built from a minimal base without dev deps
FROM ajslater/codex-base:$RUNNABLE_BASE_VERSION
ARG CODEX_WHEEL
WORKDIR /
COPY --from=codex-wheels /wheels /wheels
COPY ./dist/$CODEX_WHEEL /wheels/

# hadolint ignore=DL3013
RUN pip3 install --no-cache-dir --no-index --find-links=/wheels "/wheels/$CODEX_WHEEL"

RUN mkdir -p /comics && touch /comics/DOCKER_UNMOUNTED_VOLUME

VOLUME /comics
VOLUME /config
EXPOSE 9810
CMD ["/usr/local/bin/codex"]
