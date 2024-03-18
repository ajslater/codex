"""OPDS v1 Data classes."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class OPDS1Link:
    """An OPDS Link."""

    rel: str
    href: str
    mime_type: str
    title: str = ""
    length: int = 0
    facet_group: str = ""
    facet_active: bool = False
    thr_count: int = 0
    pse_count: int = 0
    pse_last_read: int = 0
    pse_last_read_date: datetime | None = None
