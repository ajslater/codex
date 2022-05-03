FROM ajslater/codex-builder-base:e77faf5ad2907764cf57e2697c573395-aarch64
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=dev

# hadolint ignore=DL3018
RUN apk add --no-cache \
    htop \
    npm \
    valgrind
# hadolint ignore=DL3013
RUN pip3 install --upgrade --no-cache-dir pip \
  && pip3 install --no-cache-dir --upgrade poetry
WORKDIR /app
RUN poetry config virtualenvs.in-project false
COPY pyproject.toml .
RUN poetry update
