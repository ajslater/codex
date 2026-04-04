"""Utility classes by many views."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import override


@dataclass
class Route:
    """Breadcrumb, like a route."""

    group: str
    pks: tuple[int, ...]
    page: int = 1
    name: str = ""

    @override
    def __hash__(self) -> int:
        """Breadcrumb hash."""
        pk_parts = tuple(sorted(set(self.pks)))
        parts = (self.group, pk_parts, self.page)
        return hash(parts)

    @override
    def __eq__(self, cmp) -> bool:
        """Breadcrumb equality."""
        return cmp and hash(self) == hash(cmp)


def pop_name(kwargs: Mapping) -> Mapping:
    """Pop name from a mapping route."""
    kwargs = dict(kwargs)
    kwargs.pop("name", None)
    return kwargs
