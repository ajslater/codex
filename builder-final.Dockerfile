ARG CODEX_BUILDER_BASE_VERSION
FROM ajslater/codex-builder-base:${CODEX_BUILDER_BASE_VERSION}
ARG HOST_CACHE_DIR
ARG CODEX_WHEEL
ARG WHEELS ./cache/packages/wheels
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=$CODEX_BUILDER_FINAL_VERSION
WORKDIR /app
# Copy in caches and link wheels
COPY $HOST_CACHE_DIR/wheels $WHEELS
COPY $HOST_CACHE_DIR/pip /root/.cache/pip
COPY $HOST_CACHE_DIR/pypoetry /root/.cache/pypoetry
RUN ./python_cacher/link_wheels_from_caches.py

# Install codex
# hadolint ignore=DL3059
RUN pip3 install --no-cache-dir --upgrade --find-links=$WHEELS pip
COPY ./dist/$CODEX_WHEEL $WHEELS/$CODEX_WHEEL
# hadolint ignore=DL3059
RUN pip3 install --no-cache-dir --find-links=$WHEELS $WHEELS/$CODEX_WHEEL
