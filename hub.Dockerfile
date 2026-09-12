###############################################################################
# docker.io/ajslater/codex: DEPRECATED mirror of the ghcr.io image.
#
# Identical layers to ghcr.io/ajslater/codex:<version>; only the image config
# differs (one ENV, two labels) so codex can tell admins to switch registries.
# No RUN steps, so no QEMU is needed to build both architectures.
# Built and pushed by the deploy-hub job in .github/workflows/ci.yml.
###############################################################################
ARG CODEX_VERSION=dev
FROM ghcr.io/ajslater/codex:${CODEX_VERSION}
LABEL org.opencontainers.image.deprecated="true" \
    org.opencontainers.image.description="DEPRECATED: this image has moved to ghcr.io/ajslater/codex"
ENV DOCKER_IMAGE_DEPRECATED=1