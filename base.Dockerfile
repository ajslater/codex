FROM ajslater/python-alpine:3.10.2-alpine3.15_0
ARG CODEX_BASE_VERSION
LABEL maintainer="AJ Slater <aj@slater.net>"
LABEL version=$CODEX_BASE_VERSION

# hadolint ignore=DL3018
RUN echo "*** install codex system runtime packages ***" && \
 apk add --no-cache \
   jpeg \
   libffi \
   libwebp \
   openssl \
   xapian-bindings-python3 \
   yaml \
   zlib

# hadolint ignore=DL3018
RUN echo "*** importing unrar from alpine 3.14 ***" && \
 apk add --no-cache \
   --repository=http://dl-cdn.alpinelinux.org/alpine/v3.14/main \
   unrar
