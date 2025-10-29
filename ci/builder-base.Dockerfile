FROM nikolaik/python-nodejs:python3.14-nodejs24
# nodejs25 blocked on bug https://github.com/nodejs/node/issues/60303
ARG CODEX_BUILDER_BASE_VERSION
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=${CODEX_BUILDER_BASE_VERSION}

# **** install codex system build dependency packages ****"
COPY ci/debian.sources /etc/apt/sources.list.d/

# hadolint ignore=DL3008
RUN apt-get clean \
  && apt-get update \
  && apt-get install --no-install-recommends -y \
    bash \
    build-essential \
    cmake \
    git \
    libimagequant0 \
    libjpeg62-turbo \
    libopenjp2-7 \
    libssl3 \
    libyaml-0-2 \
    libtiff6 \
    libwebp7 \
    python3-dev \
    ruamel.yaml.clib \
    unrar \
    zlib1g \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# hadolint ignore=DL3013,DL3042
RUN pip3 install --no-cache --upgrade pip
