ARG CODEX_BUILDER_BASE_VERSION
FROM ajslater/codex-builder-base:${CODEX_BUILDER_BASE_VERSION}
ARG CODEX_BUILDER_VERSION
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version $CODEX_BUILDER_VERSION

####################
# APP DEPENDENCIES #
####################

# **** install python app dependencies ****
# hadolint ignore=DL3022
COPY --from=ajslater/codex-wheels:latest /cache/artifacts /root/.cache/pypoetry/artifacts
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --remove-untracked 

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
