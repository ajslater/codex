ARG CODEX_BUILDER_BASE_VERSION
FROM ajslater/codex-builder-base:${CODEX_BUILDER_BASE_VERSION}
ARG CODEX_DIST_BUILDER_VERSION
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=${CODEX_DIST_BUILDER_VERSION}

# hadolint ignore=DL3008
RUN apt-get clean \
  && apt-get update \
  && apt-get install --no-install-recommends -y \
    shellcheck \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# **** install python app dependencies ****
# hadolint ignore=DL3022
COPY pyproject.toml uv.lock ./
RUN PIP_CACHE_DIR=$(pip3 cache dir) PYMUPDF_SETUP_PY_LIMITED_API=0 uv sync --no-install-project --no-dev --group lint --group test

# *** install node lint & test dependency packages ***
COPY package.json package-lock.json ./
RUN npm install

# **** install npm app dependencies ****
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install

WORKDIR /app
# **** copying source for dev build ****
COPY . .

VOLUME /app/codex/static_build
VOLUME /app/codex/static_root
VOLUME /app/dist
VOLUME /app/test-results
VOLUME /app/frontend/src/choices
