ARG INSTALL_BASE_VERSION
ARG RUNNABLE_BASE_VERSION
FROM ajslater/codex-install-base:${INSTALL_BASE_VERSION} AS codex-install

# TODO replace with:
# RUN pip3 install codex
COPY dist/*.whl /tmp/
RUN pip3 wheel /tmp/*.whl --wheel-dir=/wheels

FROM ajslater/codex-base:${RUNNABLE_BASE_VERSION}
ARG PKG_VERSION
LABEL version python${RUNNABLE_BASE_VERSION}_codex-${PKG_VERSION}

RUN echo "*** install python wheels ***"
 COPY --from=codex-install /wheels /wheels

RUN pip3 install --no-index --find-links=/wheels /wheels/codex*.whl

VOLUME /comics
VOLUME /config
EXPOSE 9810
CMD ["/usr/local/bin/codex"]
