"""Utility functions."""

from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Final

_DOCKERENV_PATH: Final = Path("/.dockerenv")
_CGROUP_PATH: Final = Path("/proc/self/cgroup")


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
