"""Utility functions."""

from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Final

from codex.settings import DOCKER_IMAGE_DEPRECATED

_DOCKERENV_PATH: Final = Path("/.dockerenv")
_CGROUP_PATH: Final = Path("/proc/self/cgroup")
_DOCKER_HUB_DEPRECATION_WARNING: Final = (
    "This is the deprecated docker.io/ajslater/codex image, republished from "
    "ghcr.io only so that it can tell you this. Change your image to "
    "ghcr.io/ajslater/codex to keep receiving updates. The tags are the same "
    "and your config and comics volumes carry over unchanged: "
    "https://codex-comic-reader.readthedocs.io/DOCKER/#migrating-from-docker-hub"
)


@cache
def is_docker() -> bool:
    """
    Is codex running inside a docker container.

    Cached: a process cannot change containers, and this is consulted
    on every version request. Containers are immutable deployments, so
    codex updates itself by being replaced with a new image, not by
    installing over itself.
    """
    try:
        return _DOCKERENV_PATH.is_file() or "docker" in _CGROUP_PATH.read_text()
    except Exception:
        return False


def log_docker_hub_deprecation(log) -> None:
    """
    Tell admins running the deprecated Docker Hub image to switch registries.

    Only that image sets the flag, so ghcr.io and native installs log
    nothing. Called at startup and once a day from the janitor's version
    check, because an admin who never opens the web UI would otherwise
    never learn that this image has stopped being the real one.
    """
    if not DOCKER_IMAGE_DEPRECATED:
        return
    log.warning(_DOCKER_HUB_DEPRECATION_WARNING)


def max_none(*args):
    """None aware math.max."""
    return max((x for x in args if x is not None), default=None)


def mapping_to_dict(data) -> dict | set | frozenset | tuple | list:
    """Convert nested Mapping objects to dicts."""
    if isinstance(data, Mapping):
        return {key: mapping_to_dict(value) for key, value in data.items()}
    if isinstance(data, list | tuple | frozenset | set):
        return type(data)(mapping_to_dict(item) for item in data)
    return data


def flatten(seq: tuple | list | frozenset | set):
    """Flatten sequence one level."""
    flattened = []
    for item in seq:
        if isinstance(item, tuple | list | set | frozenset):
            # To make recursive, instead of list could call flatten again
            flattened.extend(item)
        else:
            flattened.append(item)
    return seq.__class__(flattened)
