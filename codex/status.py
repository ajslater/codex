"""Librarian Status dataclass."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union


@dataclass
class Status:
    """Args for passing into import functions."""

    status_type: Union[str, Enum]
    complete: Optional[int] = None
    total: Optional[int] = None
    since: float = 0.0
    subtitle: str = ""

    def __post_init__(self):
        """Convert enums to values."""
        if isinstance(self.status_type, Enum):
            self.status_type = self.status_type.value

    def increment_complete(self):
        """Increment complete handling None."""
        if self.complete is None:
            self.complete = 0
        self.complete += 1

    def decrement_total(self):
        """Decreent total if not not."""
        if self.total is not None:
            self.total = max(self.total - 1, 0)
