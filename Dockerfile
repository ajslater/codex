FROM python:alpine

RUN \
echo "**** install system packages ****" && \
 apk add --no-cache \
 build-base=0.5-r1 \
 libffi-dev=3.2.1-r6 \
 zlib-dev=1.2.11-r3 \
 jpeg-dev=8-r6 \
 git


RUN apk add --no-cache \
  openssl-dev

RUN apk add --no-cache \
 yaml-dev

RUN \
 echo "**** install poetry ****" && \
 pip3 install --no-cache-dir -U poetry

WORKDIR /app
RUN echo "**** copying source ****"
COPY . .
RUN echo "**** install ****" && \
 poetry install --no-dev
# comic box deps
VOLUME /comics
VOLUME /config
EXPOSE 8000
CMD ["./docker-run.sh"]
