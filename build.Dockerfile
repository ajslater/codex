ARG BUILDER_VERSION
FROM ajslater/codex-builder:${BUILDER_VERSION}
LABEL version $BUILDER_VERSION

ARG DEBIAN_FRONTEND=noninteractive

####################
# APP DEPENDENCIES #
####################

RUN echo "**** install python app dependencies ****"
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --remove-untracked

# hadolint ignore=DL3059
RUN echo "**** install npm app dependencies ****"
COPY frontend/package.json frontend/package-lock.json /app/frontend/
WORKDIR /app/frontend
RUN npm install

WORKDIR /app
RUN echo "**** copying source for dev build ****"
COPY . .

VOLUME /app/test-results
VOLUME /app/dist
