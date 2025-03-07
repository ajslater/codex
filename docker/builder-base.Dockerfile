ARG CODEX_BASE_VERSION
# hadolint ignore=DL3007
FROM ajslater/codex-base:${CODEX_BASE_VERSION}
ARG CODEX_BUILDER_BASE_VERSION
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=${CODEX_BUILDER_BASE_VERSION}

# hadolint ignore=DL4006
RUN curl -fsSL https://deb.nodesource.com/setup_23.x | bash -o pipefail -s --

# **** install codex system build dependency packages ****"
# hadolint ignore=DL3008
RUN apt-get clean \
  && apt-get update \
  && apt-get install --no-install-recommends -y \
    bash \
    build-essential \
    git \
    npm \
    python3-dev \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY builder-requirements.txt ./
# hadolint ignore=DL3013,DL3042
RUN pip3 install --no-cache --upgrade pip \
  && pip3 install --no-cache --requirement builder-requirements.txt
