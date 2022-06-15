FROM ajslater/python-alpine:3.10.5-alpine3.16_1
ARG CODEX_BASE_VERSION
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=$CODEX_BASE_VERSION

# hadolint ignore=DL3018
RUN echo "@old http://dl-cdn.alpinelinux.org/alpine/v3.14/main" >> /etc/apk/repositories && \
  apk add --no-cache \
    jpeg \
    libffi \
    libwebp \
    openssl \
    poppler-utils \
    unrar@old \
    xapian-bindings-python3 \
    yaml \
    zlib
