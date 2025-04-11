FROM ajslater/codex-builder-base:bf76176cecc7837ce0d34351087e1089-aarch64
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
RUN poetry config virtualenvs.in-project false
COPY pyproject.toml .
RUN poetry update
