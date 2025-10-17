FROM ajslater/codex-builder-base:latest-aarch64
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=dev

# hadolint ignore=DL3008
RUN apt-get clean \
  && apt-get update \
  && apt-get install --no-install-recommends -y \
    htop \
    neovim \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# hadolint ignore=DL3059,DL3013
RUN pip3 install --upgrade --no-cache-dir \
  pip

WORKDIR /app
COPY pyproject.toml .
RUN uv sync --no-install-project --all-extras --upgrade
