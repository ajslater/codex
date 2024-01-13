FROM ajslater/python-debian:3.12.1-slim-bookworm_0
ARG CODEX_BASE_VERSION
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=$CODEX_BASE_VERSION

COPY docker/debian.sources /etc/apt/sources.list.d/
# hadolint ignore=DL3008
RUN apt-get clean \
  && apt-get update \
  && apt-get install --no-install-recommends -y \
    libimagequant0 \
    libjpeg62-turbo \
    libopenjp2-7 \
    libssl3 \
    libtiff6 \
    libwebp7 \
    mupdf \
    unrar \
    zlib1g \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*
