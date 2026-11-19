"""
Reading list choices, shared by the backend and the frontend.

The frontend reads the source labels from the generated
``reading-list-choices.json``, so each label is written once, here.
"""

from types import MappingProxyType
from typing import Final

from django.db.models.enums import TextChoices


class ReadingListSourceKind(TextChoices):
    """
    Where a source's entries came from.

    A closed vocabulary defined here, so telemetry may bucket counts by it.
    """

    TAGS = "tags", "File Tags"
    UPLOAD = "upload", "Upload"
    URL = "url", "URL"
    CATALOG = "catalog", "DieselTech Catalog"
    METRON_LIST = "metron_list", "Metron Reading List"
    METRON_ARC = "metron_arc", "Metron Story Arc"
    COMICVINE_ARC = "comicvine_arc", "Comic Vine Story Arc"


SOURCE_LABELS: Final[MappingProxyType[str, str]] = MappingProxyType(
    {str(value): str(label) for value, label in ReadingListSourceKind.choices}
)
# A list card's caption names its sources briefly: ``Tags + Metron · CBRO``.
SOURCE_SHORT_LABELS: Final[MappingProxyType[str, str]] = MappingProxyType(
    {
        ReadingListSourceKind.TAGS.value: "Tags",
        ReadingListSourceKind.UPLOAD.value: "Upload",
        ReadingListSourceKind.URL.value: "URL",
        ReadingListSourceKind.CATALOG.value: "DieselTech",
        ReadingListSourceKind.METRON_LIST.value: "Metron",
        ReadingListSourceKind.METRON_ARC.value: "Metron Arc",
        ReadingListSourceKind.COMICVINE_ARC.value: "Comic Vine Arc",
    }
)
READING_LIST_CHOICES: Final = MappingProxyType({"source_kinds": SOURCE_LABELS})
