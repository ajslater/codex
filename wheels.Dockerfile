ARG WHEEL_BUILDER_VERSION
FROM ajslater/codex-wheel-builder:${WHEEL_BUILDER_VERSION}
# build binary wheels in a dev environment for each arch
ARG WHEELS_VERSION
ARG BUILDPLATFORM
ARG TARGETPLATFORM
ENV REQ_FN /app/requirements.txt
LABEL version $WHEELS_VERSION
RUN echo "Running on $BUILDPLATFORM, building for $TARGETPLATFORM" && \
    echo "Stage 1: build wheels"

WORKDIR /app
COPY poetry.lock pyproject.toml ./
RUN poetry export --without-hashes --extras wheel --output "$REQ_FN"

WORKDIR /wheels
RUN CRYPTOGRAPHY_DONT_BUILD_RUST=1 pip3 wheel -r "$REQ_FN"
