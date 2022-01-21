ARG CODEX_WHEELS_VERSION
ARG CODEX_BUILDER_VERSION
FROM ajslater/codex-wheels:${CODEX_WHEELS_VERSION} as codex-wheels
FROM ajslater/codex-builder:${CODEX_BUILDER_VERSION}
LABEL version $CODEX_BUILDER_VERSION
ENV REQ_FN=requirements.txt

####################
# APP DEPENDENCIES #
####################

# **** install python app dependencies ****
COPY --from=codex-wheels /cache/artifacts /root/.cache/pypoetry/artifacts
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
