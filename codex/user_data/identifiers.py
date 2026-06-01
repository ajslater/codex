"""
Stable identifiers for the sidecar.

The main DB stores polymorphic favorites and tag-filter lists as integer
PKs that won't survive a full rebuild. The sidecar replaces those PKs
with name-chain tuples (or comic paths) — values that *do* survive,
because the librarian's filesystem-driven import will re-create rows
with the same names and paths.

Identifier shape per group (the collection value names the group):

* ``comics`` (Comic): ``[comic.path]``
* ``folders`` (Folder): ``[folder.path]``
* ``publishers`` (Publisher): ``[publisher.name]``
* ``imprints`` (Imprint): ``[publisher.name, imprint.name]``
* ``series`` (Series): ``[publisher.name, imprint.name, series.name]``
* ``volumes`` (Volume): ``[publisher.name, imprint.name, series.name, volume.name, volume.number_to]``
* ``arcs`` (Story Arc): ``[story_arc.name]``

Tag filter lists in :class:`SettingsBrowserFilters` JSONField columns
get rewritten from ``[pk, ...]`` to ``[name, ...]`` per column. Some
columns hold scalar values (year, decade, file_type, ...) and pass
through unchanged.
"""

from __future__ import annotations

import json
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from codex.group import Group

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


def encode_identifier(group: str, parts: list[Any]) -> str:
    """JSON-encode an identifier tuple for use as a sidecar primary-key column."""
    # ``separators`` produces compact output so equal tuples encode identically.
    return json.dumps([group, *parts], separators=(",", ":"))


def decode_identifier(blob: str) -> tuple[str, list[Any]]:
    """Reverse of :func:`encode_identifier`. Returns ``(group, parts)``."""
    parsed = json.loads(blob)
    if not isinstance(parsed, list) or not parsed:
        msg = f"malformed identifier: {blob!r}"
        raise ValueError(msg)
    group = parsed[0]
    parts = parsed[1:]
    return group, parts


# Per-group part extractors. Keys are the collection values from
# :data:`codex.models.favorite.FAVORITE_MODEL_GROUP_CODES` (a ``Group``
# member hashes equal to its collection-name value, so a plain-string
# lookup finds it). Each callable takes the row instance and returns the
# identifier ``parts`` list. Pulled out of an ``if``/``elif`` chain to
# keep cyclomatic complexity in check; the lambdas use cached FK access
# (publisher / imprint / series are loaded by ``select_related`` in
# callers).
_IDENTIFIER_PART_BUILDERS: Final[MappingProxyType[str, Callable[[Any], list[Any]]]] = (
    MappingProxyType(
        {
            Group.COMIC: lambda obj: [str(obj.path)],
            Group.FOLDER: lambda obj: [str(obj.path)],
            Group.PUBLISHER: lambda obj: [obj.name],
            Group.ARC: lambda obj: [obj.name],
            Group.IMPRINT: lambda obj: [obj.publisher.name, obj.name],
            Group.SERIES: lambda obj: [obj.publisher.name, obj.imprint.name, obj.name],
            Group.VOLUME: lambda obj: [
                obj.publisher.name,
                obj.imprint.name,
                obj.series.name,
                obj.name,
                obj.number_to,
            ],
        }
    )
)


def identifier_for_browse_group(group: str, instance: Model) -> list[Any]:
    """
    Build the name-chain identifier ``parts`` for a browse-group instance.

    Raises ``ValueError`` for unknown groups. Callers wrap in try/except —
    sidecar failures must never raise into request paths.
    """
    builder = _IDENTIFIER_PART_BUILDERS.get(group)
    if builder is None:
        msg = f"unknown browse-group: {group!r}"
        raise ValueError(msg)
    return builder(instance)
