# 🐳 Codex Docker Image

Codex is a web server comic book browser and reader.

## Documentation, Source, and Issue Reports

[Codex on GitHub](https://github.com/ajslater/codex)

## Usage

Here are some example snippets to help you get started creating a container from
this image.

### docker

```sh
docker create \
    --name=codex \
    -p 9810:9810 \
    -e PUID=501 \
    -e PGID=20 \
    -v /host/path/to/config:/config \
    -v /host/path/to/comics:/comics \
    --restart unless-stopped \
    docker.io/ajslater/codex
```

### compose.yaml

```yaml
services:
    codex:
        image: docker.io/ajslater/codex
        container_name: codex
        env_file: .env
        volumes:
            - /host/path/to/config:/config
            - /host/path/to/comics:/comics:ro
        ports:
            - "9810:9810"
        restart: on-failure
        healthcheck:
            test: ["CMD", "curl", "--fail", "http://localhost:9810/health"]
            interval: 30s
            timeout: 10s
            retries: 3
            start_period: 15s
```

Special volume setup for a CIFS share:

```yaml
services:
    my-service:
        volumes:
            - nas-share:/container-path

volumes:
    nas-share:
        driver_opts:
            type: cifs
            o: "username=[username],password=[password]"
            device: //my-nas-network-name/share
```

### Environment Variables Unique to Docker

- `PUID`: Sets the UID for the default user on startup
- `PGID`: Sets the GID for the default user on startup

### General Codex Environment Variables

- `LOGLEVEL` will change how verbose codex's logging is. Valid values are
  `ERROR`, `WARNING`, `INFO`, `VERBOSE`, `DEBUG`. The default is `INFO`.
- `TIMEZONE` or `TZ` will explicitly the timezone in long format (e.g.
  `"America/Los Angeles"`). This is useful inside Docker because codex cannot
  automatically detect the host machine's timezone.
- `CODEX_CONFIG_DIR` will set the path to codex config directory. Defaults to
  `$CWD/config`
- `CODEX_RESET_ADMIN=1` will reset the admin user and its password to defaults
  when codex starts.

More environment variables documented in the
[Codex README](https://github.com/ajslater/codex?tab=readme-ov-file#environment-variables)

### Support Info

Shell access whilst the container is running:

```sh
docker exec -it codex /bin/bash
```

Monitor the logs of the container in realtime:

```sh
docker logs -f codex
```

Container version number

```sh
docker inspect -f '{{ index .Config.Labels "version" }}' codex
```

Image version number

```sh
docker inspect -f '{{ index .Config.Labels "version" }}' ajslater/codex
```

## Docker Image

[This Document](https://hub.docker.com/r/ajslater/codex)
