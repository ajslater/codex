ARG BASE_VERSION
FROM ajslater/python-alpine:$BASE_VERSION AS codex-install

RUN echo "**** install system wheel building packages ****" && \
 apk add --no-cache \
   bsd-compat-headers \
   build-base \
   libffi-dev \
   libwebp-dev \
   openssl-dev \
   yaml-dev \
   jpeg-dev \
   zlib-dev

RUN pip3 install wheel
# TODO replace with:
# RUN pip3 install codex
COPY dist/*.whl /tmp/
RUN pip3 wheel /tmp/*.whl --wheel-dir=/wheels

FROM ajslater/python-alpine:$BASE_VERSION
LABEL version python${BASE_VERSION}_codex-${PKG_VERSION}

RUN echo "*** install system runtime packages ***" && \
 apk add --no-cache \
   libffi \
   libwebp \
   openssl \
   yaml \
   jpeg \
   zlib \
   unrar

RUN echo "*** install python wheels ***"
COPY --from=codex-install /wheels /wheels

RUN pip3 install --no-index --find-links=/wheels /wheels/codex*.whl

VOLUME /comics
VOLUME /config
EXPOSE 9810
CMD ["/usr/local/bin/codex"]
