FROM python:alpine

# TODO audit these to see if we really need them all
RUN \
echo "**** install system packages ****" && \
 apk add --no-cache \
   bsd-compat-headers \
   build-base \
   libffi-dev \
   nodejs \
   npm \
   openssl-dev \
   yaml-dev \
   jpeg-dev \
   zlib-dev

RUN \
 echo "**** install poetry ****" && \
 pip3 install --no-cache-dir -U poetry

WORKDIR /app
RUN echo "**** copying source ****"
COPY . .
RUN echo "**** install api ****" && \
 poetry install --no-dev

WORKDIR /app/codex_vue
RUN echo "**** install ui packages ***" && \
  npm install && \
  npm install --dev

RUN echo "**** build vue ui ***" && \
  npm run build

WORKDIR /app

# TODO copy installed app and install non-dev libs for multi-stage build

VOLUME /comics
VOLUME /config
EXPOSE 8000
CMD ["./docker-run.sh"]
