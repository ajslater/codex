"""OPDS v1 Entry Data classes."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass
class OPDS1EntryObject:
    """Fake entry db object for top link & facet entries."""

    group: str = ""
    ids: frozenset[int] = frozenset()
    name: str = ""
    summary: str = ""
    fake: bool = True


@dataclass
class OPDS1EntryData:
    """Entry Data class to avoid to many args."""

    acquisition_groups: frozenset
    zero_pad: int
    metadata: bool
    mime_type_map: Mapping[str, str]
