"""Utility classes by many views."""

from collections.abc import Mapping
from dataclasses import dataclass

from typing_extensions import override


@dataclass
class Route:
    """Breadcrumb, like a route."""

    group: str
    pks: tuple[int, ...]
    page: int = 1
    name: str = ""

    @override
    def __hash__(self):
        """Breadcrumb hash."""
        pk_parts = tuple(sorted(set(self.pks)))
        parts = (self.group, pk_parts, self.page)
        return hash(parts)

    @override
    def __eq__(self, cmp):
        """Breadcrumb equality."""
        return cmp and hash(self) == hash(cmp)

    def __and__(self, cmp):
        """Breadcrumb intersection."""
        return (
            bool(cmp is not None)
            and (self.group == cmp.group)
            and (self.pks == cmp.pks or (set(self.pks) & set(cmp.pks)))
        )


def pop_name(kwargs: Mapping):
    """Pop name from a mapping route."""
    kwargs = dict(kwargs)
    kwargs.pop("name", None)
    return kwargs
