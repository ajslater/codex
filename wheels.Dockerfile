ARG CODEX_BUILDER_VERSION
FROM ajslater/codex-builder:${CODEX_BUILDER_VERSION} as wheels-builder
# build binary wheels in a dev environment for each arch
ARG BUILDPLATFORM
ARG TARGETPLATFORM
ENV PIP_CACHE_WHEELS /root/.cache/pip/wheels
ENV REQ_FN /app/requirements.txt
ENV WHEELS /wheels
RUN echo "Running on $BUILDPLATFORM, building for $TARGETPLATFORM" && \
    echo "Stage 1: build wheels"

WORKDIR /app
COPY poetry.lock pyproject.toml /app/
RUN poetry install --no-root --remove-untracked
COPY ./harvest_wheels.py /app/
RUN ./harvest_wheels.py /cache

# hadolint ignore=DL3007
FROM tianon/true:latest
ARG WHEELS_VERSION
LABEL version $WHEELS_VERSION
COPY --from=wheels-builder /cache /cache
