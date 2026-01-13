FROM ajslater/python-debian:3.14.2-slim-trixie_0
ARG CODEX_BASE_VERSION
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=$CODEX_BASE_VERSION

COPY ci/debian.sources /etc/apt/sources.list.d/

# hadolint ignore=DL3008
RUN apt-get clean \
  && apt-get update \
  && apt-get install --no-install-recommends -y \
    curl \
    libimagequant0 \
    libjpeg62-turbo \
    libopenjp2-7 \
    libssl3 \
    libyaml-0-2 \
    libtiff6 \
    libwebp7 \
    ruamel.yaml.clib \
    unrar \
    zlib1g \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# hadolint ignore=DL3013,DL3042
RUN pip3 install --no-cache --upgrade pip
