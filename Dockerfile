ARG WHEEL_BUILDER_VERSION
ARG RUNNABLE_BASE_VERSION
FROM ajslater/codex-wheel-builder:${WHEEL_BUILDER_VERSION} AS codex-wheels
# build binary wheels in a dev environment for each arch
ARG PKG_VERSION
ARG BUILDPLATFORM
ARG TARGETPLATFORM
RUN echo "Running on $BUILDPLATFORM, building for $TARGETPLATFORM"
RUN echo "Stage 1: build wheels"

COPY ./dist /dist

RUN mkdir -p /wheels
RUN CRYPTOGRAPHY_DONT_BUILD_RUST=1 pip3 wheel "/dist/codex-${PKG_VERSION}-py3-none-any.whl" --wheel-dir=/wheels

FROM ajslater/codex-base:${RUNNABLE_BASE_VERSION}
# The runnable enviroment built from a minimal base without dev deps
ARG PKG_VERSION
LABEL version v${PKG_VERSION}
ARG BUILDPLATFORM
ARG TARGETPLATFORM
RUN echo "Running on $BUILDPLATFORM, building for $TARGETPLATFORM"
RUN echo "Stage 1: install wheels"

RUN echo "*** install python wheels ***"
COPY --from=codex-wheels /wheels /wheels

# hadolint ignore=DL3013
RUN pip3 install --no-cache-dir --no-index --find-links=/wheels /wheels/codex*.whl

VOLUME /comics
VOLUME /config
EXPOSE 9810
CMD ["/usr/local/bin/codex"]
