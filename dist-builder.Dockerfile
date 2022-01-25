ARG CODEX_BUILDER_BASE_VERSION
FROM ajslater/codex-builder-base:${CODEX_BUILDER_BASE_VERSION}
ARG CODEX_DIST_BUILDER_VERSION
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version $CODEX_DIST_BUILDER_VERSION

####################
# APP DEPENDENCIES #
####################

# **** install python app dependencies ****
# hadolint ignore=DL3022
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN PIP_CACHE_DIR=$(pip3 cache dir) poetry install --no-root --remove-untracked 

# *** install node lint & test dependency packages ***
COPY package.json package-lock.json ./
RUN npm install

# **** install npm app dependencies ****
COPY frontend/package.json frontend/package-lock.json /app/frontend/
WORKDIR /app/frontend
RUN npm install

WORKDIR /app
# **** copying source for dev build ****
COPY . .

VOLUME /app/codex/static_build
VOLUME /app/codex/static_root
VOLUME /app/dist
VOLUME /app/test-results
