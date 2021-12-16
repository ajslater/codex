ARG WHEEL_BUILDER_VERSION
FROM ajslater/codex-wheel-builder:${WHEEL_BUILDER_VERSION}
# build binary wheels in a dev environment for each arch
ARG WHEELS_VERSION
ARG BUILDPLATFORM
ARG TARGETPLATFORM
LABEL version $WHEELS_VERSION
RUN echo "Running on $BUILDPLATFORM, building for $TARGETPLATFORM" && \
    echo "Stage 1: build wheels"

WORKDIR /wheels
COPY ./requirements.txt ./

RUN mkdir -p /wheels && \
    CRYPTOGRAPHY_DONT_BUILD_RUST=1 pip3 wheel -r ./requirements.txt --wheel-dir=/wheels
