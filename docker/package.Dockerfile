FROM ajslater/codex-base:latest-aarch64
ARG PKG_VERSION
ENV PKG_VERSION=${PKG_VERSION}
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=$PKG_VERSION

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
ENV WHEEL=codex-${PKG_VERSION}-py3-none-any.whl
WORKDIR /
COPY dist/${WHEEL} .
RUN pip3 install --no-cache-dir ./${WHEEL}

VOLUME /comics
VOLUME /config
VOLUME /dist
EXPOSE 9810
CMD ["/usr/local/bin/codex"]
