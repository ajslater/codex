"""Link constants."""

from types import MappingProxyType

from codex.librarian.scribe.importer.const import (
    CREDITS_FIELD_NAME,
    IDENTIFIERS_FIELD_NAME,
    STORY_ARC_NUMBERS_FIELD_NAME,
)
from codex.models.base import BaseModel
from codex.models.groups import Imprint, Series, Volume

COMPLEX_MODEL_FIELD_NAMES = (
    CREDITS_FIELD_NAME,
    STORY_ARC_NUMBERS_FIELD_NAME,
    IDENTIFIERS_FIELD_NAME,
)
DEFAULT_KEY_RELS = ("name",)
GROUP_KEY_RELS: MappingProxyType[type[BaseModel], tuple[str, ...]] = MappingProxyType(
    {
        Imprint: ("publisher__name", "name"),
        Series: ("publisher__name", "imprint__name", "name"),
        Volume: (
            "publisher__name",
            "imprint__name",
            "series__name",
            "name",
            "number_to",
        ),
    }
)
