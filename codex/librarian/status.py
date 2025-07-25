"""Librarian Status dataclass."""

from abc import ABC
from dataclasses import dataclass
from time import time
from typing import ClassVar

from humanize import intword, naturaldelta


@dataclass
class Status(ABC):
    """Keep track of librarians status in memory."""

    CODE: ClassVar[str]
    VERB: ClassVar[str]
    ITEM_NAME: ClassVar[str]
    SINGLE: ClassVar[bool] = False
    _title: ClassVar[str] = ""
    _verbed: ClassVar[str] = ""

    complete: int | None = None
    total: int | None = None
    since_updated: float = 0.0
    subtitle: str = ""
    start_time: float | None = None
    log_success: bool = False

    @classmethod
    def title(cls):
        """Return created title."""
        if not cls._title:
            title_parts = (cls.VERB, *cls.ITEM_NAME.split(" "))
            title_parts = (part.capitalize() for part in title_parts)
            cls._title = " ".join(title_parts)
        return cls._title

    @classmethod
    def verbed(cls):
        """Return verbed, create it if it doesn't exist."""
        if not cls._verbed:
            cls._verbed = cls.VERB + "d"
        return cls._verbed

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

    def per_second(self):
        """Items per second."""
        if self.SINGLE or self.total is None:
            return ""
        elapsed = self._elapsed()
        ips = intword(self.total / elapsed) if elapsed else "infinite"
        return f"{ips} {self.ITEM_NAME} per second"

    def reset(self):
        """Reset for batch statii."""
        self.complete = 0
        self.total = 0
        self.start()
