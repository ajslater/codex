###############################################################################
# Multi-stage Dockerfile for Codex CI and production
#
# Targets:
#   dist-builder  – CI image with all deps + source (lint, test, build wheel)
#   final         – Slim production image (default)
#
# Usage:
#   CI:    docker build --target dist-builder -t dist-builder:ci .
#          docker run dist-builder:ci make lint
#   Prod:  docker build --build-arg CODEX_WHEEL=codex-X.Y.Z-py3-none-any.whl \
#            --build-arg CODEX_VERSION=X.Y.Z .
###############################################################################

# ---- Stage 1: runtime-base (slim, no build tools) --------------------------
FROM ajslater/python-debian:3.14.3-slim-trixie_0 AS runtime-base
LABEL maintainer="AJ Slater <aj@slater.net>"

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

# ---- Stage 2: builder (build tools + Node for compilation) -----------------
FROM nikolaik/python-nodejs:python3.14-nodejs24 AS builder
# nodejs25 blocked on bug https://github.com/nodejs/node/issues/60303
LABEL maintainer="AJ Slater <aj@slater.net>"

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

# ---- Stage 3: dist-builder (all deps + source for CI) ---------------------
FROM builder AS dist-builder

# hadolint ignore=DL3008
RUN apt-get clean \
    && apt-get update \
    && apt-get install --no-install-recommends -y \
        shellcheck \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps (cacheable when lockfiles unchanged)
COPY pyproject.toml uv.lock ./
# hadolint ignore=DL3042
RUN PIP_CACHE_DIR=$(pip3 cache dir) PYMUPDF_SETUP_PY_LIMITED_API=0 \
    uv sync --no-install-project --no-dev --group lint --group test

# Root Node deps (eslint, prettier, etc.)
COPY package.json package-lock.json ./
RUN npm install

# Frontend Node deps
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install

# Full source
WORKDIR /app
COPY . .

VOLUME /app/codex/static_build
VOLUME /app/codex/static
VOLUME /app/dist
VOLUME /app/test-results
VOLUME /app/frontend/src/choices

# ---- Stage 4: wheel-installer (compile native extensions) ------------------
FROM builder AS wheel-installer
ARG CODEX_WHEEL
COPY dist/${CODEX_WHEEL} /tmp/${CODEX_WHEEL}
# hadolint ignore=DL3059,DL3013
RUN PYMUPDF_SETUP_PY_LIMITED_API=0 pip3 install --no-cache-dir /tmp/${CODEX_WHEEL}

# ---- Stage 5: final (production image) ------------------------------------
FROM runtime-base AS final
ARG CODEX_VERSION
LABEL version=$CODEX_VERSION

RUN mkdir -p /comics && touch /comics/DOCKER_UNMOUNTED_VOLUME
RUN mkdir -p /home/abc/.config/comicbox \
    && chown -R abc /home/abc/.config \
    && chmod 777 /home/abc/.config /home/abc/.config/comicbox

COPY --from=wheel-installer /usr/local /usr/local

VOLUME /comics
VOLUME /config
EXPOSE 9810
CMD ["/usr/local/bin/codex"]
