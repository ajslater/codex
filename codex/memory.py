"""Detect how much memory we're working with."""

import resource
from contextlib import suppress
from pathlib import Path

from psutil import virtual_memory

# cgroups1
MEMORY_STAT_PATH = "/sys/fs/cgroup/memory/memory.stat"

# cgroups2
MEMORY_MAX_PATH = "/sys/fs/cgroup/memory.max"

DIVISORS = {"b": 1, "k": 1024, "m": 1024**2, "g": 1024**3}


def get_cgroups2_mem_limit():
    """Get mem limit from cgroups2."""
    with Path(MEMORY_MAX_PATH).open("r") as limit:
        return int(limit.read())


def get_cgroups1_mem_limit():
    """Get mem limit from cgroups1."""
    with Path(MEMORY_STAT_PATH).open("r") as mem_stat_file:
        for line in mem_stat_file:
            parts = line.split()
            if not parts or len(parts) < 2:  # noqa PLR2004
                continue
            if "hierarchical_memory_limit" in parts[0]:
                return int(parts[1])
    return None


def get_mem_limit(divisor="b"):
    """Get the current memlimit.

    If we're in a container set the limit too.
    """
    mem_limit = None
    api_funcs = (get_cgroups2_mem_limit, get_cgroups1_mem_limit)
    for func in api_funcs:
        with suppress(Exception):
            mem_limit = func()
        if mem_limit:
            break
    if mem_limit:
        # Set the process memlimit.
        resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))

    if not mem_limit:
        # get the raw host memory
        mem_limit = virtual_memory().total
    return mem_limit / DIVISORS.get(divisor, 1)
