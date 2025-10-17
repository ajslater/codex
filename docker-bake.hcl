target "codex-base" {
    cache-from = [
      "type=registry,ref=docker.io/ajslater/codex-base:buildcache",
      "type=registry,ref=docker.io/ajslater/codex-base:latest"
    ]
    cache-to = [
      "type=registry,ref=docker.io/ajslater/codex-base:buildcache,mode=max"
    ]
    dockerfile = "base.Dockerfile"
    tags = [
      "docker.io/ajslater/codex-base:${CODEX_BASE_VERSION}",
      "docker.io/ajslater/codex-base:latest"
    ]
    platforms = ["$ARCH"]
    outputs = [ "registry" ]
}

target "codex-builder-base" {
    inherits = ["codex-base"]
    cache-from = [
      "type=registry,ref=docker.io/ajslater/codex-builder-base:buildcache",
      "type=registry,ref=docker.io/ajslater/codex-builder-base:latest"
    ]
    cache-to = [
      "type=registry,ref=docker.io/ajslater/codex-builder-base:buildcache,mode=max"
    ]
    dockerfile = "builder-base.Dockerfile"
    tags = [
      "codex-builder-base:${CODEX_BUILDER_BASE_VERSION}",
      "codex-builder-base:latest"
    ]
    outputs = [ "registry" ]
}

target "codex-dist-builder" {
    inherits = ["codex-base"]
    cache-from = [
      "type=registry,ref=docker.io/ajslater/codex-dist-builder:buildcache",
      "type=registry,ref=docker.io/ajslater/codex-dist-builder:latest"
    ]
    cache-to = [
      "type=registry,ref=docker.io/ajslater/codex-dist-builder:buildcache,mode=max"
    ]
    dockerfile = "dist-builder.Dockerfile"
    tags = [
      "docker.io/ajslater/codex-dist-builder:${CODEX_DIST_BUILDER_VERSION}",
      "docker.io/ajslater/codex-dist-builder:latest"
    ]
    outputs = [ "docker", "registry" ]
}

target "codex-arch" {
    inherits = ["codex-base"]
    cache-from = [
      "type=docker,ref=docker.io/ajslater/codex-arch:buildcache",
      "type=docker,ref=docker.io/ajslater/codex-arch:${CODEX_ARCH_LATEST}"
    ]
    cache-to = [
      "type=docker,ref=docker.io/ajslater/codex-arch:buildcache,mode=max"
    ]
    dockerfile = "Dockerfile"
    args = {
        BUILDX_EXPERIMENTAL = 1,
        CODEX_BUILDER_FINAL_VERSION,
        CODEX_WHEEL,
        PKG_VERSION
    }
    tags = [
      "docker.io/ajslate/codex-arch:${CODEX_ARCH_VERSION}"
      "docker.io/ajslate/codex-arch:${CODEX_ARCH_LATEST}"
    ]
    outputs = [ "docker" ]
  }
