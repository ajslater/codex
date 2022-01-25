ARG CODEX_BASE_VERSION
FROM ajslater/codex-base:${CODEX_BUILDER_BASE_VERSION} as codex-base-installer
ARG HOST_CACHE_DIR
ARG CODEX_WHEEL
ARG WHEELS ./cache/packages/wheels
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=$CODEX_BUILDER_FINAL
WORKDIR /
# Copy in caches and codex wheel
COPY $HOST_CACHE_DIR/pip /root/.cache/pip
COPY $HOST_CACHE_DIR/pypoetry /root/.cache/pypoetry
COPY ./link_wheels_from_caches.py save_py_caches.py ./
RUN ./link_wheels_from_caches.py
COPY ./dist/$CODEX_WHEEL $WHEELS/$CODEX_WHEEL

# Install codex
RUN pip3 install --no-cache-dir --upgrade --find-links=$WHEELS pip
# hadolint ignore=DL3059
RUN pip3 install --no-cache-dir --find-links=$WHEELS $WHEELS/$CODEX_WHEEL
