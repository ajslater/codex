"""Custom url converters."""

from types import MappingProxyType

from django.urls.converters import StringConverter
from loguru import logger

# v4 collection segment (plural English) → v3 single-char group code.
# Used for favorites and custom-cover uploads where the segment names
# the resource directly.
#
# For browse listings, the same mapping doubles as the v3 nav-group
# kwarg: v4 ``/browse/{collection}/{parentIds}`` translates to v3
# ``(group=collection-letter, pks=parentIds)``. v3 then advances
# ``model_group`` to the next visible level based on the user's
# ``show`` settings (the "next group" rule). That means
# ``/browse/series/5`` reads as "navigate from series 5" the same way
# v3's ``/s/5/1`` did — the URL noun names the *current* nav level,
# not the listing target. The plan's example wording ("series under
# publishers 5,7") describes the user-facing intent; the dispatcher
# is the v3 ``model_group`` chain underneath.
COLLECTION_TO_GROUP = MappingProxyType(
    {
        "publishers": "p",
        "imprints": "i",
        "series": "s",
        "volumes": "v",
        "comics": "c",
        "folders": "f",
        "arcs": "a",
    }
)


class CollectionConverter(StringConverter):
    """Validate v4 collection segment (plural English collection name)."""

    regex = r"publishers|imprints|series|volumes|comics|folders|arcs"


class IntListConverter:
    """Integer list converter."""

    regex = r"\d+(,\d+)*"
    DELIMITER = ","

    def to_python(self, value) -> tuple:
        """Convert string list to tuple of ints."""
        parts = value.split(self.DELIMITER)
        pks = set()
        for part in parts:
            try:
                pk = int(part)
                if pk == 0:
                    pks = set()
                    break
                pks.add(pk)
            except ValueError:
                reason = f"Bad pk list submitted to IntConverter {part=} in {value=}"
                logger.warning(reason)

        return tuple(sorted(pks))

    def to_url(self, value) -> str:
        """Convert sequence of ints to a comma delineated string list."""
        pks: set[str] = set()
        if value:
            for pk in sorted(value):
                if pk == 0:
                    pks = set()
                    break
                pks.add(str(pk))
        return self.DELIMITER.join(pks) if pks else "0"
