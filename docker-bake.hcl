variable "ARCH" {}
variable "CODEX_ARCH_VERSION" {}
variable "CODEX_BASE_VERSION" {}
variable "CODEX_BUILDER_BASE_VERSION" {}
variable "CODEX_DIST_BUILDER_VERSION" {}
variable "CODEX_WHEEL" {}
variable "PKG_VERSION" {}

target "codex-base" {
    cache-from = [
      "type=registry,ref=docker.io/ajslater/codex-base:buildcache",
      "type=registry,ref=docker.io/ajslater/codex-base:latest-${ARCH}"
    ]
    cache-to = [
      "type=registry,ref=docker.io/ajslater/codex-base:buildcache,mode=max"
    ]
    dockerfile = "docker/base.Dockerfile"
    tags = [
      "docker.io/ajslater/codex-base:${CODEX_BASE_VERSION}",
      "docker.io/ajslater/codex-base:latest-${ARCH}"
    ]
    platforms = ["${ARCH}"]
    output = [ "type=registry" ]
}

target "codex-builder-base" {
    inherits = ["codex-base"]
    cache-from = [
      "type=registry,ref=docker.io/ajslater/codex-builder-base:buildcache",
      "type=registry,ref=docker.io/ajslater/codex-builder-base:latest-${ARCH}"
    ]
    cache-to = [
      "type=registry,ref=docker.io/ajslater/codex-builder-base:buildcache,mode=max"
    ]
    dockerfile = "docker/builder-base.Dockerfile"
    tags = [
      "docker.io/ajslater/codex-builder-base:${CODEX_BUILDER_BASE_VERSION}",
      "docker.io/ajslater/codex-builder-base:latest-${ARCH}"
    ]
    output = [ "type=registry" ]
}

target "codex-dist-builder" {
    inherits = ["codex-builder-base"]
    args = {
      CODEX_BUILDER_BASE_VERSION = CODEX_BUILDER_BASE_VERSION
    }
    cache-from = [
      "type=registry,ref=docker.io/ajslater/codex-dist-builder:buildcache",
      "type=registry,ref=docker.io/ajslater/codex-dist-builder:latest-${ARCH}"
    ]
    cache-to = [
      "type=registry,ref=docker.io/ajslater/codex-dist-builder:buildcache,mode=max"
    ]
    dockerfile = "docker/dist-builder.Dockerfile"
    tags = [
      "docker.io/ajslater/codex-dist-builder:${CODEX_DIST_BUILDER_VERSION}",
      "docker.io/ajslater/codex-dist-builder:latest-${ARCH}"
    ]
    output = [ "type=docker", "type=registry" ]
}

target "codex-arch" {
    inherits = ["codex-builder-base"]
    args = {
      CODEX_BASE_VERSION = CODEX_BASE_VERSION
      CODEX_BUILDER_BASE_VERSION = CODEX_BUILDER_BASE_VERSION
      CODEX_WHEEL = CODEX_WHEEL
      PKG_VERSION = PKG_VERSION
    }
    cache-from = [
      "type=registry,ref=docker.io/ajslater/codex:latest"
    ]
    cache-to = []
    dockerfile = "docker/Dockerfile"
    tags = [
      "docker.io/ajslater/codex-arch:${CODEX_ARCH_VERSION}",
      #"docker.io/ajslate/codex-arch:${CODEX_ARCH_LATEST}"
    ]
    output = [ "type=registry" ]
  }
