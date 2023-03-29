"""Detect how much memory we're working with."""
import resource
from pathlib import Path

from psutil import virtual_memory

# just alpine path for now.
LINUX_MEMORY_LIMIT_PATHS = ("/sys/fs/cgroup/memory.max",)

DIVISORS = {"b": 1, "k": 1024, "m": 1024**2, "g": 1024**3}


def get_mem_limit(divisor="b"):
    """Get the current memlimit.

    If we're in an alpine container set the limit too.
    """
    mem_limit = 0
    for path_str in LINUX_MEMORY_LIMIT_PATHS:
        path = Path(path_str)
        try:
            if path.is_file():
                with path.open("r") as limit:
                    mem = int(limit.read())
                if not mem:
                    break

                # Set the process memlimit.
                resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
                mem_limit = mem
                break
        except Exception:  # noqa: S110
            pass
    if not mem_limit:
        mem_limit = virtual_memory().total
    return mem_limit / DIVISORS.get(divisor, 1)
