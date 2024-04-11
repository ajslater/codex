"""Librarian Status dataclass."""

from dataclasses import dataclass
from enum import Enum


@dataclass
class Status:
    """Args for passing into import functions."""

    status_type: str | Enum
    complete: int | None = None
    total: int | None = None
    since: float = 0.0
    subtitle: str = ""

    def __post_init__(self):
        """Convert enums to values."""
        if isinstance(self.status_type, Enum):
            self.status_type = self.status_type.value

    def add_complete(self, count: int):
        """Add count to complete."""
        if self.complete is None:
            self.complete = 0
        self.complete += count

    def increment_complete(self):
        """Increment complete handling None."""
        self.add_complete(1)

    def decrement_total(self):
        """Decreent total if not not."""
        if self.total is not None:
            self.total = max(self.total - 1, 0)
