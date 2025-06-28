"""Librarian Status dataclass."""

from dataclasses import dataclass
from enum import Enum
from time import time

from humanize import intword, naturaldelta


@dataclass
class Status:
    """Keep track of librarians status in memory."""

    status_type: Enum
    complete: int | None = None
    total: int | None = None
    since: float = 0.0
    subtitle: str = ""
    start_time: float | None = None

    def increment_complete(self, count: int = 1):
        """Add count to complete."""
        self.complete = self.complete + count if self.complete else count

    def decrement_total(self):
        """Decrement total if not not."""
        self.total = max(self.total - 1, 0) if self.total is not None else None

    def start(self):
        """Set start time."""
        self.start_time = time()

    def _elapsed(self):
        return time() - self.start_time if self.start_time else 0

    def elapsed(self):
        """Elapsed time."""
        return naturaldelta(self._elapsed())

    def per_second(self, plural_name: str, num=None):
        """Items per second."""
        if num is None:
            num = self.total
        if num is None:
            return ""
        elapsed = self._elapsed()
        ips = intword(num / elapsed) if elapsed else "infinite"
        return f"{ips} {plural_name} per second."

    def reset(self):
        """Reset for batch statii."""
        self.complete = 0
        self.total = 0
        self.start()
