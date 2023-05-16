"""OPDS v1 Entry Data classes."""
from dataclasses import dataclass


@dataclass
class OPDS1EntryObject:
    """Fake entry db object for top link & facet entries."""

    group: str = ""
    pk: int = 0
    name: str = ""
    summary: str = ""
    fake: bool = True


@dataclass
class OPDS1EntryData:
    """Entry Data class to avoid to many args."""

    acquisition_groups: frozenset
    issue_max: int
    metadata: bool
    mime_type_map: dict
