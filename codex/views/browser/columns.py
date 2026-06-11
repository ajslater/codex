"""
Helpers around the browser table-view column registry.

The registry itself lives in :mod:`codex.choices.browser` so the choices
JSON build pipeline can pick it up. This module provides the runtime
helpers used by the views, serializers, and validators.
"""

from types import MappingProxyType
from typing import cast

from django.db.models import (
    Aggregate,
    BooleanField,
    Case,
    F,
    Q,
    Value,
    When,
)
from django.db.models.fields import CharField
from django.db.models.functions import Concat

from codex.choices.browser import (
    BROWSER_TABLE_COLUMNS,
    BROWSER_TABLE_DEFAULT_COLUMNS,
)
from codex.models.favorite import FAVORITE_MODEL_COLLECTIONS, Favorite
from codex.models.functions import JsonGroupArray

# ORM paths or expressions for M2M columns. Simple ones map a single
# ``related__name`` path; ``credits`` and ``identifiers`` need composite
# strings since the related model carries multiple fields the user
# wants to see together.
_M2M_CREDIT_EXPR = Case(
    # ``credits__role`` is nullable. When it's missing we render just
    # the person's name; when it's set we suffix " (Role)" so the
    # frontend gets ready-to-display strings without a per-cell join.
    When(
        credits__role__isnull=True,
        then=F("credits__person__name"),
    ),
    default=Concat(
        F("credits__person__name"),
        Value(" ("),
        F("credits__role__name"),
        Value(")"),
    ),
    output_field=CharField(),
)

_M2M_IDENTIFIER_EXPR = Case(
    # Render ``[source:]type:key`` so the frontend can show readable
    # composite identifiers without a follow-up join. ``source`` is
    # nullable; drop the leading ``:`` when it is missing.
    When(
        identifiers__source__isnull=True,
        then=Concat(
            F("identifiers__id_type"),
            Value(":"),
            F("identifiers__key"),
        ),
    ),
    default=Concat(
        F("identifiers__source__name"),
        Value(":"),
        F("identifiers__id_type"),
        Value(":"),
        F("identifiers__key"),
    ),
    output_field=CharField(),
)

_M2M_COLUMN_PATHS = MappingProxyType(
    {
        "characters": "characters__name",
        "credits": _M2M_CREDIT_EXPR,
        "genres": "genres__name",
        "identifiers": _M2M_IDENTIFIER_EXPR,
        "locations": "locations__name",
        "series_groups": "series_groups__name",
        "stories": "stories__name",
        "story_arcs": "story_arc_numbers__story_arc__name",
        "tags": "tags__name",
        "teams": "teams__name",
        "universes": "universes__name",
    }
)

# Per-column aggregate filters. Comics can carry M2M rows whose
# fields are empty (e.g. a placeholder identifier with no source /
# type / key, an unnamed credit person). Without these filters the
# composite expressions render as ``":"`` or empty strings and pollute
# the aggregated list. Aggregates support a ``filter`` kwarg that
# scopes the aggregation to matching rows; filter rows here are the
# rows we *want* to include.
_M2M_AGGREGATE_FILTERS = MappingProxyType(
    {
        "credits": Q(credits__person__name__gt=""),
        "identifiers": Q(identifiers__id_type__gt="") | Q(identifiers__key__gt=""),
    }
)

# FK-name columns: their value is a single related model's ``name``.
# All keys here also collide with a Comic FK field (``country``,
# ``language``, ``age_rating``, etc.) or aren't already covered by
# ``annotate_collection_names``, so we annotate via a prefixed alias and
# read it back through ``fk_alias_for``.
_FK_NAME_COLUMN_PATHS = MappingProxyType(
    {
        "imprint_name": "imprint__name",
        "country": "country__name",
        "language": "language__name",
        "original_format": "original_format__name",
        "tagger": "tagger__name",
        "scan_info": "scan_info__name",
        "age_rating": "age_rating__name",
        "main_character": "main_character__name",
        "main_team": "main_team__name",
    }
)


def default_columns_for(top_collection: str) -> tuple[str, ...]:
    """Return the default column tuple for a top-collection, or empty if unknown."""
    # The defaults map is keyed by collection name now, matching the
    # engine's collection-valued ``top_collection`` — a direct lookup.
    return BROWSER_TABLE_DEFAULT_COLUMNS.get(top_collection, ())


# Default columns gated on the matching ``show.<key>`` collection flag.
# A user who hides imprints / volumes from breadcrumb navigation
# almost certainly doesn't want the corresponding column to lead
# their default column set either; filtering the defaults keeps the
# new-user experience tracking the user's hierarchy preferences.
_SHOW_GATED_COLUMNS: MappingProxyType[str, str] = MappingProxyType(
    {
        "imprint_name": "imprints",
        "volume_name": "volumes",
    }
)


def default_columns_filtered(
    top_collection: str, show: object | None = None
) -> tuple[str, ...]:
    """
    Return ``default_columns_for(top_collection)`` minus show-gated columns.

    ``show`` is the per-user collection-flag dict from
    ``BrowserSettingsShowCollectionFlagsSerializer`` (collection keys
    ``publishers``, ``imprints``, ``series``, ``volumes``). When a flag
    is False or missing, the matching
    column is dropped from the defaults — a user who hides imprints
    in navigation rarely wants the imprint column to lead their
    table-view defaults. Static ``default_columns_for`` stays
    unchanged for tests / migrations that need the canonical tuple.
    """
    cols = default_columns_for(top_collection)
    if not cols:
        return cols
    show_map: dict = show if isinstance(show, dict) else {}
    blocked = {
        col for col, flag in _SHOW_GATED_COLUMNS.items() if not show_map.get(flag)
    }
    if not blocked:
        return cols
    return tuple(c for c in cols if c not in blocked)


def is_sortable(column_key: str) -> bool:
    """Return True when clicking the column header should drive ``order_by``."""
    entry = BROWSER_TABLE_COLUMNS.get(column_key)
    return bool(entry and entry["sort_key"])


def is_m2m(column_key: str) -> bool:
    """Return True when the column's value comes from a Many-to-Many relation."""
    entry = BROWSER_TABLE_COLUMNS.get(column_key)
    return bool(entry and entry["m2m"])


def sort_key_for(column_key: str) -> str | None:
    """Return the ``order_by`` enum key the column maps to, or None."""
    entry = BROWSER_TABLE_COLUMNS.get(column_key)
    if entry is None:
        return None
    # Registry values are heterogeneous (str | bool | None); narrow here.
    return cast("str | None", entry["sort_key"])


# Annotation aliases must not collide with Comic field names
# (``Comic.genres``, ``Comic.tags``, etc. are existing ManyToManyField
# attributes, so ``qs.annotate(genres=...)`` raises). Prefix the
# annotation alias and have :func:`m2m_alias_for` provide the
# round-trip; ``_row_repr`` reads via this alias.
_M2M_ANNOTATION_PREFIX = "_table_m2m_"


def m2m_alias_for(column_key: str) -> str:
    """Return the queryset annotation alias for an M2M column key."""
    return _M2M_ANNOTATION_PREFIX + column_key


def m2m_annotations_for(columns: tuple[str, ...]) -> dict[str, Aggregate]:
    """
    Build a dict of ``alias -> JsonGroupArray`` for requested M2M columns.

    Only columns whose ORM path is known (see ``_M2M_COLUMN_PATHS``)
    contribute an annotation. Other M2M columns are deferred and stay
    null in the response. The empty dict is meaningful: it tells the
    caller "skip the M2M annotation step entirely".

    Each aggregate gets a ``filter=`` Q so JSON_GROUP_ARRAY doesn't
    fold ``NULL``-row LEFT JOIN results into the array as JSON nulls.
    Comics with no M2M relations would otherwise produce ``[null]``
    instead of ``[]``, breaking the empty-cell equivalence we need
    for sorting. Columns listed in ``_M2M_AGGREGATE_FILTERS`` use
    that custom filter (for the composite credits/identifiers
    expressions); simple-path columns get a default isnull filter.

    ``order_by=path`` sorts each row's array elements alphabetically,
    so two rows with the same M2M set produce the same JSON literal
    — load-bearing for the M2M-sort feature where ``ORDER BY alias``
    relies on identical sets having identical aggregate strings.
    """
    annotations: dict[str, Aggregate] = {}
    for col in columns:
        path = _M2M_COLUMN_PATHS.get(col)
        if path is None:
            continue
        kwargs: dict = {"distinct": True, "order_by": path}
        agg_filter = _M2M_AGGREGATE_FILTERS.get(col)
        if agg_filter is None and isinstance(path, str):
            agg_filter = Q(**{f"{path}__isnull": False})
        if agg_filter is not None:
            kwargs["filter"] = agg_filter
        annotations[m2m_alias_for(col)] = JsonGroupArray(path, **kwargs)
    return annotations


def m2m_columns() -> frozenset[str]:
    """Return the set of M2M column keys whose annotation is wired."""
    return frozenset(_M2M_COLUMN_PATHS.keys())


# FK-name annotations live in their own alias namespace so they don't
# collide with the matching Comic FK field attributes (``country`` /
# ``language`` / etc.).
_FK_ANNOTATION_PREFIX = "_table_fk_"


def fk_alias_for(column_key: str) -> str:
    """Return the queryset annotation alias for an FK-name column key."""
    return _FK_ANNOTATION_PREFIX + column_key


def fk_name_annotations_for(columns: tuple[str, ...]) -> dict[str, F]:
    """Build ``alias -> F`` annotations for requested FK-name columns."""
    annotations: dict[str, F] = {}
    for col in columns:
        path = _FK_NAME_COLUMN_PATHS.get(col)
        if path is not None:
            annotations[fk_alias_for(col)] = F(path)
    return annotations


def fk_name_columns() -> frozenset[str]:
    """Return the set of FK-name column keys whose annotation is wired."""
    return frozenset(_FK_NAME_COLUMN_PATHS.keys())


_FAVORITE_FALSE = Value(value=False, output_field=BooleanField())
_FAVORITE_TRUE = Value(value=True, output_field=BooleanField())


def favorite_annotation_for(model, user) -> dict:
    """
    Build the ``favorite`` annotation for a browser queryset.

    Returns a dict that's safe to splat into ``qs.annotate(**...)``:

    * a ``Case-When-In`` boolean for authenticated users on a
      favorite-able model — SQLite materializes the favorited-id
      subquery once and runs a hash-set membership check per row,
      slightly cheaper than the equivalent correlated ``Exists``;
    * a constant ``Value(False)`` for anonymous sessions, so the
      schema stays uniform whether the column is sortable or just
      rendered;
    * an empty dict when ``model`` isn't in the favorite-able set —
      the table-view caller passes a known model so this branch is
      rare in practice.
    """
    collection_code = FAVORITE_MODEL_COLLECTIONS.get(model)
    if collection_code is None:
        return {}
    if not user or not user.is_authenticated:
        return {"favorite": _FAVORITE_FALSE}
    # ``.value``: binding the Collection StrEnum member itself makes
    # cachalot's parameter-type check raise UncachableQuery for every
    # query this subquery lands in — silently uncaching all browse
    # queries. The bound SQL value is identical either way.
    favorited_ids = Favorite.objects.filter(
        user=user, collection=collection_code.value
    ).values("target_id")
    return {
        "favorite": Case(
            When(pk__in=favorited_ids, then=_FAVORITE_TRUE),
            default=_FAVORITE_FALSE,
            output_field=BooleanField(),
        ),
    }
