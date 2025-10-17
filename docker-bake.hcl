variable "CODEX_BASE_VERSION" {}
variable "CODEX_BUILDER_BASE_VERSION" { default = ""}
variable "CODEX_DIST_BUILDER_VERSION" {}
variable "CODEX_ARCH_VERSION" {}
variable "ARCH" {}

target "codex-base" {
    cache-from = [
      "type=registry,ref=docker.io/ajslater/codex-base:buildcache",
      "type=registry,ref=docker.io/ajslater/codex-base:latest"
    ]
    cache-to = [
      "type=registry,ref=docker.io/ajslater/codex-base:buildcache,mode=max"
    ]
    dockerfile = "docker/base.Dockerfile"
    tags = [
      "docker.io/ajslater/codex-base:${CODEX_BASE_VERSION}",
      "docker.io/ajslater/codex-base:latest"
    ]
    platforms = ["${ARCH}"]
    outputs = [ "type=registry" ]
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
    dockerfile = "docker/builder-base.Dockerfile"
    tags = [
      "docker.io/ajslater/codex-builder-base:${CODEX_BUILDER_BASE_VERSION}",
      "docker.io/ajslater/codex-builder-base:latest"
    ]
    outputs = [ "type=registry" ]
}

target "codex-dist-builder" {
    inherits = ["codex-builder-base"]
    args = {
      CODEX_BUILDER_BASE_VERSION = "${CODEX_BUILDER_BASE_VERSION}"
    }
    cache-from = [
      "type=registry,ref=docker.io/ajslater/codex-dist-builder:buildcache",
      "type=registry,ref=docker.io/ajslater/codex-dist-builder:latest"
    ]
    cache-to = [
      "type=registry,ref=docker.io/ajslater/codex-dist-builder:buildcache,mode=max"
    ]
    dockerfile = "docker/dist-builder.Dockerfile"
    tags = [
      "docker.io/ajslater/codex-dist-builder:${CODEX_DIST_BUILDER_VERSION}",
      "docker.io/ajslater/codex-dist-builder:latest"
    ]
    outputs = [ "type=docker", "type=registry" ]
}

target "codex-arch" {
    inherits = ["codex-builder-base"]
    cache-from = [
      "type=docker,ref=docker.io/ajslater/codex-arch:buildcache",
      #"type=docker,ref=docker.io/ajslater/codex-arch:${CODEX_ARCH_LATEST}"
    ]
    cache-to = [
      "type=docker,ref=docker.io/ajslater/codex-arch:buildcache,mode=max"
    ]
    dockerfile = "docker/Dockerfile"
    tags = [
      "docker.io/ajslate/codex-arch:${CODEX_ARCH_VERSION}",
      #"docker.io/ajslate/codex-arch:${CODEX_ARCH_LATEST}"
    ]
    outputs = [ "type=docker" ]
  }
