FROM nikolaik/python-nodejs:python3.13-nodejs23
ARG CODEX_BUILDER_BASE_VERSION
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=${CODEX_BUILDER_BASE_VERSION}

# hadolint ignore=DL4006
RUN curl -fsSL https://deb.nodesource.com/setup_23.x | bash -o pipefail -s --

# **** install codex system build dependency packages ****"
COPY docker/debian.sources /etc/apt/sources.list.d/
# hadolint ignore=DL3008
RUN apt-get clean \
  && apt-get update \
  && apt-get install --no-install-recommends -y \
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
    bash \
    build-essential \
    git \
    python3-dev \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY builder-requirements.txt ./
# hadolint ignore=DL3013,DL3042
RUN pip3 install --no-cache --upgrade pip \
  && pip3 install --no-cache --requirement builder-requirements.txt
