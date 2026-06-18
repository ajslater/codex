"""Detect how much memory we're working with."""

import resource
from contextlib import suppress
from pathlib import Path
from types import MappingProxyType
from typing import Final

from psutil import virtual_memory

# cgroups1
MEMORY_STAT_PATH: Final = Path("/sys/fs/cgroup/memory/memory.stat")

# cgroups2
MEMORY_MAX_PATH: Final = Path("/sys/fs/cgroup/memory.max")

DIVISORS: Final = MappingProxyType({"b": 1, "k": 1024, "m": 1024**2, "g": 1024**3})
# Each line in memory.stat is "<key> <value>"; anything shorter is malformed.
_MIN_STAT_PARTS: Final = 2


def _get_cgroups2_mem_limit() -> int:
    """Get mem limit from cgroups2."""
    with MEMORY_MAX_PATH.open("r") as limit:
        return int(limit.read())


def _get_cgroups1_mem_limit() -> int | None:
    """Get mem limit from cgroups1."""
    with MEMORY_STAT_PATH.open("r") as mem_stat_file:
        for line in mem_stat_file:
            parts = line.split()
            if len(parts) < _MIN_STAT_PARTS:
                continue
            if "hierarchical_memory_limit" in parts[0]:
                return int(parts[1])
    return None


def _detect_cgroup_limit() -> int | None:
    """Return the container memory limit in bytes, or None outside a cgroup."""
    for func in (_get_cgroups2_mem_limit, _get_cgroups1_mem_limit):
        with suppress(Exception):
            if limit := func():
                return limit
    return None


def read_mem_limit(divisor="b") -> float:
    """
    Read the memory budget (cgroup limit, else host RAM) with no side effects.

    Unlike :func:`get_mem_limit`, this never mutates the process ``RLIMIT_AS``,
    so it's safe to call from request workers (e.g. the admin backup endpoint)
    that must not pin their own address space.
    """
    mem_limit = _detect_cgroup_limit() or virtual_memory().total
    return mem_limit / DIVISORS.get(divisor, 1)


def get_mem_limit(divisor="b"):
    """
    Get the current memlimit.

    If we're in a container set the process ``RLIMIT_AS`` too.
    """
    cgroup_limit = _detect_cgroup_limit()
    if cgroup_limit:
        # Pin the process memlimit to the container's.
        resource.setrlimit(resource.RLIMIT_AS, (cgroup_limit, cgroup_limit))
    mem_limit = cgroup_limit or virtual_memory().total
    return mem_limit / DIVISORS.get(divisor, 1)
