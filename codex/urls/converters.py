"""Custom url converters."""

from types import MappingProxyType

from django.urls.converters import StringConverter
from loguru import logger

# v4 collection segment (plural English) → v3 single-char group code.
# Keep in sync with ``codex.views.v4.browse.COLLECTION_TO_GROUP``; the
# converter only validates the regex, the view does the translation.
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


class GroupConverter(StringConverter):
    """Only accept valid browser groups."""

    regex = r"[rpisvcfa]"


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
