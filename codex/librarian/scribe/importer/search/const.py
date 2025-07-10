"""Search import consts."""

from types import MappingProxyType

from codex.serializers.fields.browser import CountryField, LanguageField

_COMICFTS_ATTRIBUTES = (
    "collection_title",
    "file_type",
    "issue",
    "name",
    "notes",
    "reading_direction",
    "review",
    "summary",
    "updated_at",
)
_COMICFTS_FKS = (
    "publisher",
    "imprint",
    "series",
    "age_rating",
    "country",
    "language",
    "original_format",
    "scan_info",
    "tagger",
)
_COMICFTS_M2MS = (
    "characters",
    "credits",
    "genres",
    "identifiers",
    "locations",
    "series_groups",
    "sources",
    "stories",
    "story_arcs",
    "tags",
    "teams",
    "universes",
)
COMICFTS_UPDATE_FIELDS = (
    *_COMICFTS_ATTRIBUTES,
    *_COMICFTS_FKS,
    *_COMICFTS_M2MS,
)
PYCOUNTRY_FIELDS = MappingProxyType(
    {"country": CountryField(), "language": LanguageField()}
)
