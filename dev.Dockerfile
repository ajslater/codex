FROM ajslater/codex-builder-base:f316b80100df28f87f16b7411ecbbc58-aarch64
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=dev

# hadolint ignore=DL3018,DL3013
RUN apk add --no-cache \
    htop \
    npm && \
    pip3 install --upgrade --no-cache-dir pip
WORKDIR /app
RUN poetry config virtualenvs.in-project false
COPY pyproject.toml .
RUN poetry update
