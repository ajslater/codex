"""
Stable identifiers for the sidecar.

The main DB stores polymorphic favorites and tag-filter lists as integer
PKs that won't survive a full rebuild. The sidecar replaces those PKs
with name-chain tuples (or comic paths) — values that *do* survive,
because the librarian's filesystem-driven import will re-create rows
with the same names and paths.

Identifier shape per group char:

* ``c`` (Comic): ``[comic.path]``
* ``f`` (Folder): ``[folder.path]``
* ``p`` (Publisher): ``[publisher.name]``
* ``i`` (Imprint): ``[publisher.name, imprint.name]``
* ``s`` (Series): ``[publisher.name, imprint.name, series.name]``
* ``v`` (Volume): ``[publisher.name, imprint.name, series.name, volume.name, volume.number_to]``
* ``a`` (Story Arc): ``[story_arc.name]``

Tag filter lists in :class:`SettingsBrowserFilters` JSONField columns
get rewritten from ``[pk, ...]`` to ``[name, ...]`` per column. Some
columns hold scalar values (year, decade, file_type, ...) and pass
through unchanged.
"""

from __future__ import annotations

import json
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.db.models import Model


# Tag filter column → main-DB tag model. Lazily imported via string
# refs to keep this module importable before django.setup(). Resolved
# on first use by :func:`tag_model_for_filter`. Filter columns absent
# from this mapping are scalar (decade, year, file_type, ...) and pass
# through unchanged.
_FILTER_TAG_MODEL_REFS: Final[MappingProxyType[str, str]] = MappingProxyType(
    {
        "age_rating_metron": "codex.AgeRatingMetron",
        "age_rating_tagged": "codex.AgeRating",
        "characters": "codex.Character",
        "country": "codex.Country",
        # ``credits`` filters by CreditPerson PK on the ORM side
        # (see ``codex.views.browser.filters.field._FILTER_REL_MAP``).
        "credits": "codex.CreditPerson",
        "genres": "codex.Genre",
        "identifier_source": "codex.IdentifierSource",
        "language": "codex.Language",
        "locations": "codex.Location",
        "original_format": "codex.OriginalFormat",
        "series_groups": "codex.SeriesGroup",
        "stories": "codex.Story",
        "story_arcs": "codex.StoryArc",
        "tagger": "codex.Tagger",
        "tags": "codex.Tag",
        "teams": "codex.Team",
        "universes": "codex.Universe",
    }
)
FILTER_TAG_COLUMNS: Final[frozenset[str]] = frozenset(_FILTER_TAG_MODEL_REFS)


def tag_model_for_filter(column: str) -> type[Model] | None:
    """Return the tag model class for a filter column, or ``None`` if scalar."""
    ref = _FILTER_TAG_MODEL_REFS.get(column)
    if ref is None:
        return None
    from django.apps import apps

    app_label, model_name = ref.split(".", 1)
    return apps.get_model(app_label, model_name)


def encode_identifier(group_char: str, parts: list[Any]) -> str:
    """JSON-encode an identifier tuple for use as a sidecar primary-key column."""
    # ``separators`` produces compact output so equal tuples encode identically.
    return json.dumps([group_char, *parts], separators=(",", ":"))


def decode_identifier(blob: str) -> tuple[str, list[Any]]:
    """Reverse of :func:`encode_identifier`. Returns ``(group_char, parts)``."""
    parsed = json.loads(blob)
    if not isinstance(parsed, list) or not parsed:
        msg = f"malformed identifier: {blob!r}"
        raise ValueError(msg)
    group_char = parsed[0]
    parts = parsed[1:]
    return group_char, parts


# Per-group-char part extractors. Keys are the polymorphic group chars
# from :data:`codex.models.favorite.FAVORITE_MODEL_GROUP_CODES`. Each
# callable takes the row instance and returns the identifier ``parts``
# list. Pulled out of an ``if``/``elif`` chain to keep cyclomatic
# complexity in check; the lambdas use cached FK access (publisher /
# imprint / series are loaded by ``select_related`` in callers).
_IDENTIFIER_PART_BUILDERS: Final[MappingProxyType[str, Callable[[Any], list[Any]]]] = (
    MappingProxyType(
        {
            "c": lambda obj: [str(obj.path)],
            "f": lambda obj: [str(obj.path)],
            "p": lambda obj: [obj.name],
            "a": lambda obj: [obj.name],
            "i": lambda obj: [obj.publisher.name, obj.name],
            "s": lambda obj: [obj.publisher.name, obj.imprint.name, obj.name],
            "v": lambda obj: [
                obj.publisher.name,
                obj.imprint.name,
                obj.series.name,
                obj.name,
                obj.number_to,
            ],
        }
    )
)


def identifier_for_browse_group(group_char: str, instance: Model) -> list[Any]:
    """
    Build the name-chain identifier ``parts`` for a browse-group instance.

    Raises ``ValueError`` for unknown group chars. Callers wrap in
    try/except — sidecar failures must never raise into request paths.
    """
    builder = _IDENTIFIER_PART_BUILDERS.get(group_char)
    if builder is None:
        msg = f"unknown browse-group char: {group_char!r}"
        raise ValueError(msg)
    return builder(instance)
