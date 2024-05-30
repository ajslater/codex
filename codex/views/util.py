"""Utility classes by many views."""

from dataclasses import asdict, dataclass


@dataclass()
class Route(dict):
    """Breadcrumb, like a route."""

    group: str
    pks: tuple[int, ...]
    page: int = 1
    name: str = ""

    def __eq__(self, cmp):
        """Breadcrumb equality."""
        return (
            bool(cmp is not None)
            and (self.group == cmp.group)
            and (set(self.pks) == set(cmp.pks))
        )

    def __and__(self, cmp):
        """Breadcrumb intersection."""
        return (
            bool(cmp is not None)
            and (self.group == cmp.group)
            and (set(self.pks) & set(cmp.pks))
        )

    dict = asdict
