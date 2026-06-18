"""Custom url converters."""

from django.urls.converters import StringConverter
from loguru import logger


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
