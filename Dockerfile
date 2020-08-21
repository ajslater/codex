FROM python:alpine AS codex-install

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

FROM python:alpine

RUN echo "*** UID/GID Init. TODO move to a base image ***"
COPY docker/etc/cont-init.d /etc/
RUN apk add --no-cache shadow
RUN echo "*** create default user ***" && \
  adduser --uid 911 --home /config --shell /bin/false --disabled-password abc && \
  usermod -G users abc

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
USER abc
CMD ["codex"]
