ARG CODEX_BASE_VERSION
# hadolint ignore=DL3007
FROM ajslater/codex-base:${CODEX_BASE_VERSION}
ARG CODEX_BUILDER_VERSION
ARG TARGETPLATFORM
ENV CODEX_WHEELS /wheels
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=${CODEX_BUILDER_VERSION}

WORKDIR /
# **** install codex system build dependency packages ****"
# hadolint ignore=DL3018
RUN apk add --no-cache \
   bash \
   bsd-compat-headers \
   build-base \
   cargo \
   git \
   jpeg-dev \
   libffi-dev \
   libwebp-dev \
   musl-dev \
   npm \
   openssl-dev \
   python3-dev \
   rust \
   xapian-bindings-python3 \
   xapian-core-dev \
   yaml-dev \
   zlib-dev

WORKDIR /app
COPY vendor/shellcheck ./vendor/shellcheck/
RUN vendor/shellcheck/install-shellcheck.sh

# *** install python build dependency packages ***
# use latest before we build a possible new wheels in the following script
# hadolint ignore=DL3022
COPY --from=ajslater/codex-wheels:latest /cache/wheels $CODEX_WHEELS
# hadolint ignore=DL3042,DL3013
RUN pip3 install --find-links=$CODEX_WHEELS --upgrade pip
# https://github.com/pyca/cryptography/issues/6673#issuecomment-985943023
# old hash on this index was 1285ae84e5963aae
RUN git clone --bare --depth 1 https://github.com/rust-lang/crates.io-index.git /root/.cargo/registry/index/github.com-1ecc6299db9ec823
COPY builder-requirements.txt ./
# hadolint ignore=DL3042
RUN pip3 install --find-links=$CODEX_WHEELS --requirement builder-requirements.txt

# *** install node build dependency packages ***
COPY package.json package-lock.json ./
RUN npm install
