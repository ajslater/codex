ARG CODEX_BASE_VERSION
# hadolint ignore=DL3007
FROM ajslater/codex-base:${CODEX_BASE_VERSION}
ARG CODEX_BUILDER_BASE_VERSION
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=${CODEX_BUILDER_BASE_VERSION}

# **** install codex system build dependency packages ****"
# hadolint ignore=DL3008
RUN apt-get clean \
  && apt-get update \
  && apt-get install --no-install-recommends -y \
    bash \
    build-essential \
    git \
    npm \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*
# TODO remove cruft for debian
#  cargo \
#  libjpeg-dev \
#  libwebp-dev \
#  openssl-dev \
#  python3-dev \
#  rust \
#  swig \
#  zlib1g-dev \

WORKDIR /app

# https://github.com/pyca/cryptography/issues/6673#issuecomment-985943023
# old hash on this index was 1285ae84e5963aae
COPY builder-requirements.txt ./
# hadolint ignore=DL3013,DL3042,DL3059
#RUN git clone --bare --depth 1 \
#  https://github.com/rust-lang/crates.io-index.git \
#  /root/.cargo/registry/index/github.com-1ecc6299db9ec823 && \
# hadolint ignore=DL3013,DL3042
RUN pip3 install --no-cache --upgrade pip \
  && pip3 install --no-cache --requirement builder-requirements.txt
