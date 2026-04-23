###############################################################################
# Multi-stage Dockerfile for Codex CI and production
#
# Targets:
#   codex-ci      – CI image with all deps + source (lint, test, build wheel)
#   final         – Slim production image (default)
#
# Usage:
#   CI:    docker build --target codex-ci -t codex-ci:ci .
#          docker run codex-ci:ci make lint
#   Prod:  docker build --build-arg CODEX_WHEEL=codex-X.Y.Z-py3-none-any.whl \
#            --build-arg CODEX_VERSION=X.Y.Z .
###############################################################################

# ---- Stage 1: builder (build tools + Node for compilation) -----------------
FROM nikolaik/python-nodejs:python3.14-nodejs24 AS builder-base
# nodejs25 blocked on bug https://github.com/nodejs/node/issues/60303

COPY debian.sources /etc/apt/sources.list.d/

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

# ---- Stage 2: codex-ci (all deps + source for CI) -------------------------
# hadolint ignore=DL3007
FROM oven/bun:latest AS bun-source
FROM builder-base AS codex-ci

# hadolint ignore=DL3008
RUN apt-get clean \
    && apt-get update \
    && apt-get install --no-install-recommends -y \
        shellcheck \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=bun-source /usr/local/bin/bun /usr/local/bin/bun
COPY --from=bun-source /usr/local/bin/bunx /usr/local/bin/bunx

WORKDIR /app

# Python deps (cacheable when lockfiles unchanged)
COPY pyproject.toml uv.lock ./
# hadolint ignore=DL3042
RUN PIP_CACHE_DIR=$(pip3 cache dir) PYMUPDF_SETUP_PY_LIMITED_API=0 \
    uv sync --no-install-project --no-dev --group lint --group test

# Root Node deps (eslint, prettier, etc.)
COPY bun.lock package.json ./
RUN bun install

# Frontend Node deps
WORKDIR /app/frontend
COPY frontend/bun.lock frontend/package.json ./
RUN bun install

# Full source
WORKDIR /app
COPY . .

VOLUME /app/codex/static_build
VOLUME /app/codex/static
VOLUME /app/dist
VOLUME /app/test-results
VOLUME /app/frontend/src/choices

# ---- Stage 3: wheel-installer (compile native extensions) ------------------
FROM builder-base AS wheel-installer
ARG CODEX_WHEEL
COPY dist/${CODEX_WHEEL} /tmp/${CODEX_WHEEL}
# hadolint ignore=DL3059,DL3013
RUN PYMUPDF_SETUP_PY_LIMITED_API=0 pip3 install --no-cache-dir /tmp/${CODEX_WHEEL}

# Slim down /usr/local before it gets copied to the final image
# hadolint ignore=DL3059
RUN set -eux \
    # Remove pip, setuptools, wheel — not needed at runtime
    && pip3 uninstall -y pip setuptools wheel 2>/dev/null || true \
    && rm -rf /usr/local/bin/pip* \
    # Strip debug symbols from shared libraries (~30-50% size reduction on .so files)
    && find /usr/local -name '*.so' -exec strip --strip-unneeded {} + 2>/dev/null || true \
    && find /usr/local -name '*.so.*' -exec strip --strip-unneeded {} + 2>/dev/null || true \
    # Remove Python bytecode caches (regenerated on first import)
    && find /usr/local -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local -name '*.pyc' -delete 2>/dev/null || true \
    # Remove the stdlib test suite (~30MB) — safe, never needed at runtime
    && rm -rf /usr/local/lib/python*/test \
    && rm -rf /usr/local/lib/python*/idlelib \
    && rm -rf /usr/local/lib/python*/ensurepip \
    # Remove type stubs — only used by type checkers
    && find /usr/local -name '*.pyi' -delete 2>/dev/null || true \
    # Remove the installed wheel
    && rm -f /tmp/${CODEX_WHEEL}

# ---- Stage 4: final (production image) ------------------------------------
FROM ghcr.io/ajslater/python-debian:3.14.4-slim-trixie_0 AS final
ARG CODEX_VERSION
LABEL org.opencontainers.image.title="Codex" \
    org.opencontainers.image.description="Codex Comic Server" \
    org.opencontainers.image.version="${CODEX_VERSION}" \
    org.opencontainers.image.authors="AJ Slater <aj@slater.net>" \
    org.opencontainers.image.url="https://codex-reader.app" \
    org.opencontainers.image.source="https://github.com/ajslater/codex" \
    org.opencontainers.image.licenses="GPL-3.0-only"

COPY debian.sources /etc/apt/sources.list.d/

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

RUN mkdir -p /comics && touch /comics/DOCKER_UNMOUNTED_VOLUME
RUN mkdir -p /home/abc/.config/comicbox \
    && chown -R abc /home/abc/.config \
    && chmod 777 /home/abc/.config /home/abc/.config/comicbox

COPY --from=wheel-installer /usr/local /usr/local

VOLUME /comics
VOLUME /config
EXPOSE 9810
CMD ["/usr/local/bin/codex"]