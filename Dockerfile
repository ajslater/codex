FROM ajslater/codex-wheel-builder:$WHEEL_BUILDER_BASE_VERSION AS codex-wheels

COPY ./dist /dist

RUN mkdir -p /wheels
RUN pip3 wheel "/dist/codex-${PKG_VERSION}" --wheel-dir=/wheels

FROM ajslater/codex-base:${RUNNABLE_BASE_VERSION}
LABEL version v${PKG_VERSION}

RUN echo "*** install python wheels ***"
COPY --from=codex-wheels /wheels /wheels

# hadolint ignore=DL3013
RUN pip3 install --no-index --find-links=/wheels /wheels/codex*.whl

VOLUME /comics
VOLUME /config
EXPOSE 9810
CMD ["/usr/local/bin/codex"]
