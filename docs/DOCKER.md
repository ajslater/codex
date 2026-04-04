# 🐳 Codex Docker Image

Codex is a web server comic book browser and reader.

## Documentation, Source, and Issue Reports

- [Codex Documentation](https://codex-comic-reader.readthedocs.io/)
- [Codex Docker Images](https://github.com/ajslater/codex/pkgs/container/codex)
- [Codex Source](https://github.com/ajslater/codex)
- [Codex Issues](https://github.com/ajslater/codex/issues)

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
    ghcr.io/ajslater/codex
```

### compose.yaml

```yaml
services:
    codex:
        image: ghcr.io/ajslater/codex
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

Refer to the
[Environment Variable Docs](https://codex-comic-reader.readthedocs.io/#environment-variables)
for codex environment variables.

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
docker inspect -f '{{ index .Config.Labels "org.opencontainers.image.version" }}' codex
```

Image version number

```sh
docker inspect -f '{{ index .Config.Labels "org.opencontainers.image.version" }}' ajslater/codex
```

## Docker Image

[This Document](https://codex-comic-reader.readthedocs.io/DOCKER/)
