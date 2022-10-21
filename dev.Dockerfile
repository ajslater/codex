FROM ajslater/codex-builder-base:2f7e490820d18cb5103f7ad51f11358c-aarch64
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=dev

# hadolint ignore=DL3018
RUN apk add --no-cache \
    htop \
    npm
# hadolint ignore=DL3013
RUN pip3 install --upgrade --no-cache-dir pip \
  && pip3 install --no-cache-dir --upgrade poetry
WORKDIR /app
RUN poetry config virtualenvs.in-project false
COPY pyproject.toml .
RUN poetry update
