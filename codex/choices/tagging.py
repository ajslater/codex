"""
Choices for the metadata tag-edit panel.

Backs the format / identifier / language selectors in the frontend tag editor
(``frontend/src/components/metadata/edit-mode/edit-panel.vue``), dumped to
``frontend/src/choices/*.json`` by the sibling ``choices_to_json.py``.

Everything here is *derived* from its upstream source — comicbox's transforms
and enums, ``pycountry``, and codex's own ``IdentifierType`` — so the lists
track those sources instead of being hand-maintained. The only codex-authored
glue is the comicbox-canonical -> tag-editor field-name map
(``_CANONICAL_TO_EDITOR``, because codex normalizes a few nested comicbox
objects into flat relational fields) and the one nested sub-field comicbox's
transform specs don't surface at the top level (``_EXTRA_FORMAT_FIELDS``).
"""

from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import cast

import pycountry  # a hard dependency of comicbox
from comicbox.enums.generic import GenericFormatEnum
from comicbox.enums.maps.age_rating import COMICINFO_AGE_RATING_MAP
from comicbox.enums.metroninfo import MetronAgeRatingEnum, MetronFormatEnum
from comicbox.formats.comic_info.transform import ComicInfoTransform
from comicbox.formats.metron_info.transform import MetronInfoTransform
from comicbox.identifiers.identifiers import IdSources

from codex.choices.reader import READER_CHOICES
from codex.models.identifier import IdentifierType

# comicbox transform per codex write-format id.
_TRANSFORMS = MappingProxyType(
    {
        "COMIC_INFO": ComicInfoTransform,
        "METRON_INFO": MetronInfoTransform,
    }
)


def _vuetify_choices(pairs: Iterable[tuple[str, str]]) -> tuple[MappingProxyType, ...]:
    """Build a tuple of read-only ``{title, value}`` vuetify choices."""
    return tuple(
        MappingProxyType({"title": title, "value": value}) for title, value in pairs
    )


# ---------------------------------------------------------------------------
# Registries derived from upstream enums
# ---------------------------------------------------------------------------

# ISO 639-1 languages (title=English name, value=2-letter code), sorted by name.
LANGUAGES = _vuetify_choices(
    sorted(
        (language.name, language.alpha_2)
        for language in pycountry.languages
        if getattr(language, "alpha_2", None)
    )
)

# comicbox identifier sources (Comic Vine, Metron, GCD, ...); title == value.
IDENTIFIER_SOURCES = _vuetify_choices(
    (source.value, source.value) for source in IdSources
)

# codex identifier types; the TextChoices labels supply the UI titles
# (ARC -> "Arc", ISSUE -> "Issue", ROLE -> "Role", CREATOR -> "Creator", ...).
IDENTIFIER_TYPES = _vuetify_choices(
    (id_type.label, id_type.value) for id_type in IdentifierType
)


# ---------------------------------------------------------------------------
# Per-format field support, derived from the comicbox transforms
# ---------------------------------------------------------------------------

# comicbox canonical field name -> codex tag-editor field name(s). Identity for
# most fields; the splits/renames are codex's relational model (issue split into
# number + suffix so issues sort numerically, comicbox "arcs" stored as
# story_arcs, ComicInfo's "manga"/"title" surfaced as reading_direction/stories).
# Canonical keys absent here (bookmark, date, pages, reprints, page_count,
# prices, updated_at, ...) are not tag-editor fields and are dropped.
_CANONICAL_TO_EDITOR: MappingProxyType[str, tuple[str, ...]] = MappingProxyType(
    {
        "publisher": ("publisher",),
        "imprint": ("imprint",),
        "series": ("series",),
        "volume": ("volume", "volume_issue_count"),
        "issue": ("issue_number", "issue_suffix"),
        "summary": ("summary",),
        "review": ("review",),
        "notes": ("notes",),
        "scan_info": ("scan_info",),
        "genres": ("genres",),
        "characters": ("characters",),
        "teams": ("teams",),
        "locations": ("locations",),
        "tags": ("tags",),
        "series_groups": ("series_groups",),
        "stories": ("stories",),
        "title": ("stories",),
        "arcs": ("story_arcs",),
        "monochrome": ("monochrome",),
        "original_format": ("original_format",),
        "manga": ("reading_direction",),
        "reading_direction": ("reading_direction",),
        "credits": ("credits",),
        "language": ("language",),
        "age_rating": ("age_rating",),
        "critical_rating": ("critical_rating",),
        "protagonist": ("protagonist",),
        "identifiers": ("identifiers",),
        "country": ("country",),
        "universes": ("universes",),
    }
)

# Editor sub-fields comicbox stores only for some formats and which its
# transform specs don't surface at the SPECS_TO top level (the sole
# hand-maintained support datum): MetronInfo's Series carries a volume count.
_EXTRA_FORMAT_FIELDS: MappingProxyType[str, tuple[str, ...]] = MappingProxyType(
    {
        "METRON_INFO": ("volume_count",),
    }
)


def _canonical_keys(transform) -> tuple[str, ...]:
    """Canonical comicbox field keys a format reads/writes, in declared order."""
    # comicbox types SPECS_TO["comicbox"] loosely (dict | Coalesce); it is always
    # the canonical-key spec mapping at runtime.
    specs = cast("Mapping[str, object]", transform.SPECS_TO["comicbox"])
    return tuple(specs)


def _supported_canonical_keys(transform) -> frozenset[str]:
    """Canonical comicbox field keys a format reads/writes."""
    return frozenset(_canonical_keys(transform))


def _format_field_support() -> MappingProxyType:
    support = {}
    for fmt, transform in _TRANSFORMS.items():
        fields: list[str] = []
        seen: set[str] = set()
        for canonical_key in _canonical_keys(transform):
            for editor_field in _CANONICAL_TO_EDITOR.get(canonical_key, ()):
                if editor_field not in seen:
                    seen.add(editor_field)
                    fields.append(editor_field)
        for editor_field in _EXTRA_FORMAT_FIELDS.get(fmt, ()):
            if editor_field not in seen:
                seen.add(editor_field)
                fields.append(editor_field)
        support[fmt] = tuple(fields)
    return MappingProxyType(support)


FORMAT_FIELD_SUPPORT = _format_field_support()


# ---------------------------------------------------------------------------
# Per-format enumerated value lists, derived from comicbox enums
# ---------------------------------------------------------------------------

_READING_DIRECTION_TITLES = READER_CHOICES["READING_DIRECTION"]
# ComicInfo's Manga field only stores horizontal reading directions.
_COMICINFO_READING_DIRECTIONS = ("ltr", "rtl")
# Each format's original_format vocabulary.
_ORIGINAL_FORMAT_ENUMS = MappingProxyType(
    {
        "COMIC_INFO": GenericFormatEnum,
        "METRON_INFO": MetronFormatEnum,
    }
)
_UNKNOWN_AGE_RATING = "Unknown"


def _age_ratings() -> tuple[MappingProxyType, ...]:
    """Canonical (Metron) age ratings; ComicInfo's differing spelling under "ci"."""
    choices = []
    for rating in MetronAgeRatingEnum:
        if rating.value == _UNKNOWN_AGE_RATING:
            continue
        choice = {"title": rating.value, "value": rating.value}
        comicinfo = COMICINFO_AGE_RATING_MAP.get(rating)
        if comicinfo is not None and comicinfo.value != rating.value:
            choice["ci"] = comicinfo.value
        choices.append(MappingProxyType(choice))
    choices.sort(key=lambda choice: choice["title"])
    return tuple(choices)


_AGE_RATINGS = _age_ratings()


def _reading_directions(canonical_keys: frozenset[str]) -> tuple[MappingProxyType, ...]:
    if not ({"manga", "reading_direction"} & canonical_keys):
        return ()
    return _vuetify_choices(
        (_READING_DIRECTION_TITLES[code], code)
        for code in _COMICINFO_READING_DIRECTIONS
    )


def _original_formats(fmt: str, canonical_keys: frozenset[str]) -> tuple[str, ...]:
    enum = _ORIGINAL_FORMAT_ENUMS.get(fmt)
    if enum is None or "original_format" not in canonical_keys:
        return ()
    return tuple(sorted(member.value for member in enum))


def _format_field_values() -> MappingProxyType:
    values = {}
    for fmt, transform in _TRANSFORMS.items():
        keys = _supported_canonical_keys(transform)
        values[fmt] = MappingProxyType(
            {
                "age_ratings": _AGE_RATINGS if "age_rating" in keys else (),
                "original_formats": _original_formats(fmt, keys),
                "reading_directions": _reading_directions(keys),
            }
        )
    return MappingProxyType(values)


FORMAT_FIELD_VALUES = _format_field_values()
