FROM nikolaik/python-nodejs:python3.13-nodejs23
ARG CODEX_BUILDER_BASE_VERSION
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=${CODEX_BUILDER_BASE_VERSION}

# **** install codex system build dependency packages ****"
# hadolint ignore=DL3008
RUN apt-get clean \
  && apt-get update \
  && apt-get install --no-install-recommends -y \
    # Codex base
    libimagequant0 \
    libjpeg62-turbo \
    libopenjp2-7 \
    libssl3 \
    libyaml-0-2 \
    libtiff6 \
    libwebp7 \
    mupdf \
    ruamel.yaml.clib \
    unrar \
    zlib1g \
    # Builder base
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
