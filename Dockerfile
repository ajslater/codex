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
FROM nikolaik/python-nodejs:python3.14-nodejs26 AS builder-base
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
        unrar \
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

# ---- Stage 3: wheel-installer (runtime venv) --------------------------------
FROM builder-base AS wheel-installer
ARG CODEX_WHEEL=unbuilt
WORKDIR /tmp/build
COPY pyproject.toml uv.lock ./
COPY dist/${CODEX_WHEEL} ./
# Pin the runtime closure to uv.lock; install the wheel itself without deps.
RUN uv export --frozen --no-default-groups --no-emit-project -o requirements.txt \
    && uv venv --python /usr/local/bin/python3.14 /opt/codex \
    && PYMUPDF_SETUP_PY_LIMITED_API=0 uv pip install --python /opt/codex/bin/python \
        --no-cache --compile-bytecode -r requirements.txt \
    && uv pip install --python /opt/codex/bin/python --no-cache --no-deps \
        --compile-bytecode ./${CODEX_WHEEL}

# Strip debug symbols, drop type stubs, and drop every translation but
# English: LANGUAGE_CODE is en-us and nothing activates another language.
# hadolint ignore=SC2016
RUN set -eux \
    && find /opt/codex -type f \( -name '*.so' -o -name '*.so.*' \) \
        -exec strip --strip-unneeded {} + \
    && find /opt/codex -name '*.pyi' -delete \
    && rm -rf /opt/codex/lib/python3.14/site-packages/pycountry/locales \
    && find /opt/codex/lib/python3.14/site-packages -type d -name locale -prune \
        -exec sh -c 'for d in "$1"/*/; do case "$(basename "$d")" in en|__pycache__) ;; *) rm -rf "$d";; esac; done' _ {} \;

# ---- Stage 4: final (production image) ------------------------------------
FROM ghcr.io/ajslater/python-debian:3.14.6-slim-trixie_0 AS final
ARG CODEX_VERSION=dev
LABEL org.opencontainers.image.title="Codex" \
    org.opencontainers.image.description="Codex Comic Server" \
    org.opencontainers.image.version="${CODEX_VERSION}" \
    org.opencontainers.image.authors="AJ Slater <aj@slater.net>" \
    org.opencontainers.image.url="https://codex-reader.app" \
    org.opencontainers.image.source="https://github.com/ajslater/codex" \
    org.opencontainers.image.licenses="GPL-3.0-only"

COPY debian.sources /etc/apt/sources.list.d/

# Manylinux wheels (pymupdf, rapidfuzz) link the system libstdc++.so.6.
# hadolint ignore=DL3008
RUN apt-get clean \
    && apt-get update \
    && apt-get install --no-install-recommends -y \
        curl \
        libstdc++6 \
        unrar \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /comics && touch /comics/DOCKER_UNMOUNTED_VOLUME
RUN mkdir -p /home/abc/.config/comicbox \
    && chown -R abc /home/abc/.config \
    && chmod 777 /home/abc/.config /home/abc/.config/comicbox

COPY --from=wheel-installer /opt/codex /opt/codex
ENV PATH="/opt/codex/bin:${PATH}"
# Fail the build, not the container start, on a broken venv.
RUN python -B -c "import django, comicbox, pymupdf, PIL.Image, cryptography, granian, rapidfuzz"

VOLUME /comics
VOLUME /config
EXPOSE 9810
CMD ["/opt/codex/bin/codex"]