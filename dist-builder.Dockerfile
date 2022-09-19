ARG CODEX_BUILDER_BASE_VERSION
FROM ajslater/codex-builder-base:${CODEX_BUILDER_BASE_VERSION}
ARG CODEX_DIST_BUILDER_VERSION
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version $CODEX_DIST_BUILDER_VERSION

WORKDIR /app
# hadolint ignore=DL3018
RUN apk add --no-cache \
  shellcheck

# **** install python app dependencies ****
# hadolint ignore=DL3022
COPY pyproject.toml poetry.lock ./
RUN PIP_CACHE_DIR=$(pip3 cache dir) poetry install --no-root --remove-untracked --without dev


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
