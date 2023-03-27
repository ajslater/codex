"""Librarian Status dataclass."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Status:
    """Args for passing into import functions."""

    status_type: str
    complete: Optional[int] = None
    total: Optional[int] = None
    since: float = 0.0
    subtitle: str = ""

    def increment_complete(self):
        """Increment complete handling None."""
        if self.complete is None:
            self.complete = 0
        self.complete += 1

    def decrement_total(self):
        """Decreent total if not not."""
        if self.total is not None:
            self.total = max(self.total - 1, 0)
