"""
Per-group column intersections for table view.

For a group row (Series, Publisher, Volume, etc.), each column's
displayed value is the *intersection* across the group's child comics:

- M2M (genres / tags / characters / ...): values present in **every**
  child comic. Comics that don't share the value at all → empty
  cell. Same semantic as
  :class:`MetadataQueryIntersectionsView._get_m2m_intersection_query`.
- Scalar (year / country / language / file_type / monochrome / ...):
  the value if **every** child comic shares it, otherwise empty.

This is what the user asked for in the group-row table experiment.
The helper is invoked after pagination so we only compute for the
visible page; per visible column it issues one batched query that
groups results by the parent group's pk.
"""

from collections import defaultdict
from collections.abc import Iterable
from types import MappingProxyType
from typing import Any

from django.db.models import Count, Q

from codex.models import Comic
from codex.views.browser.columns import fk_name_columns, m2m_columns
from codex.views.const import MODEL_REL_MAP


def _format_credit(person_name: str, role_name: str | None) -> str:
    if role_name:
        return f"{person_name} ({role_name})"
    return person_name


def _format_identifier(source_name: str | None, id_type: str, key: str) -> str:
    if source_name:
        return f"{source_name}:{id_type}:{key}"
    return f"{id_type}:{key}"


# Comic field paths for scalar / FK-name columns that participate in
# group-row intersection. Keys mirror the column registry; values are
# Django ORM paths from Comic. Columns whose value is the group's own
# attribute (publisher_name on a Series row, etc.) are *already*
# correct via ``annotate_group_names`` and aren't computed here.
_SCALAR_FIELD_PATHS: MappingProxyType[str, str] = MappingProxyType(
    {
        # Direct Comic fields.
        "year": "year",
        "month": "month",
        "day": "day",
        "date": "date",
        "issue_number": "issue_number",
        "issue_suffix": "issue_suffix",
        "page_count": "page_count",
        "size": "size",
        "file_type": "file_type",
        "reading_direction": "reading_direction",
        "monochrome": "monochrome",
        "critical_rating": "critical_rating",
        "metadata_mtime": "metadata_mtime",
        "created_at": "created_at",
        "updated_at": "updated_at",
        "bookmark_updated_at": "bookmark_updated_at",
        # FK-to-name columns (Comic FK → related model.name).
        "country": "country__name",
        "language": "language__name",
        "original_format": "original_format__name",
        "tagger": "tagger__name",
        "scan_info": "scan_info__name",
        "age_rating": "age_rating__name",
        "main_character": "main_character__name",
        "main_team": "main_team__name",
        "imprint_name": "imprint__name",
    }
)


def compute_group_intersections(
    group_qs, columns: Iterable[str]
) -> dict[int, dict[str, Any]]:
    """
    Build ``{group_pk: {column_key: intersection_value}}`` for the page.

    ``group_qs`` should be the already-paginated group queryset. Comic
    querysets short-circuit to an empty dict — Comic rows show their
    own values, not group intersections. Columns whose value source
    isn't recognized are skipped (the row's existing value path
    applies).
    """
    cols = tuple(columns)
    if not cols or group_qs.model is Comic:
        return {}

    comic_to_group = MODEL_REL_MAP.get(group_qs.model)
    if not comic_to_group:
        return {}

    group_pks = list(group_qs.values_list("pk", flat=True))
    if not group_pks:
        return {}

    # Comic counts per group — denominator for "every comic shares this value".
    counts_qs = (
        Comic.objects.filter(**{f"{comic_to_group}__in": group_pks})
        .values(comic_to_group)
        .annotate(comic_count=Count("pk", distinct=True))
    )
    counts: dict[int, int] = {
        row[comic_to_group]: row["comic_count"] for row in counts_qs
    }

    result: dict[int, dict[str, Any]] = {pk: {} for pk in group_pks}
    m2m_set = m2m_columns()
    fk_set = fk_name_columns()

    for col in cols:
        if col in m2m_set:
            _compute_m2m_intersection(col, group_pks, comic_to_group, counts, result)
        elif col in _SCALAR_FIELD_PATHS or col in fk_set:
            path = _SCALAR_FIELD_PATHS.get(col)
            if path is None:
                continue
            _compute_scalar_intersection(
                col, path, group_pks, comic_to_group, counts, result
            )
    return result


def _compute_scalar_intersection(
    col: str,
    comic_path: str,
    group_pks: list[int],
    comic_to_group: str,
    counts: dict[int, int],
    result: dict[int, dict[str, Any]],
) -> None:
    """Set ``result[group][col]`` to the value if every comic shares it."""
    rows = (
        Comic.objects.filter(**{f"{comic_to_group}__in": group_pks})
        .values(comic_to_group, comic_path)
        .annotate(cnt=Count("pk", distinct=True))
    )
    per_group: dict[int, list[tuple[Any, int]]] = defaultdict(list)
    for row in rows:
        gpk = row[comic_to_group]
        per_group[gpk].append((row[comic_path], row["cnt"]))
    for gpk in group_pks:
        pairs = per_group.get(gpk, [])
        total = counts.get(gpk, 0)
        # Single distinct value covering every comic in the group → intersection.
        if total > 0 and len(pairs) == 1 and pairs[0][1] == total:
            result[gpk][col] = pairs[0][0]
        else:
            result[gpk][col] = None


def _compute_m2m_intersection(
    col: str,
    group_pks: list[int],
    comic_to_group: str,
    counts: dict[int, int],
    result: dict[int, dict[str, Any]],
) -> None:
    """Set ``result[group][col]`` to the list of M2M values shared by every comic."""
    # Field-specific aggregation. credits / identifiers carry composite
    # display strings (Person (Role) / source:type:key); the others map
    # to a single ``__name`` path.
    if col == "credits":
        _compute_credits_intersection(group_pks, comic_to_group, counts, result)
        return
    if col == "identifiers":
        _compute_identifiers_intersection(group_pks, comic_to_group, counts, result)
        return

    rel = _M2M_NAME_RELATIONS.get(col)
    if rel is None:
        return
    rows = (
        Comic.objects.filter(**{f"{comic_to_group}__in": group_pks})
        .filter(**{f"{rel}__isnull": False})
        .values(comic_to_group, rel)
        .annotate(cnt=Count("pk", distinct=True))
    )
    per_group: dict[int, list[tuple[Any, int]]] = defaultdict(list)
    for row in rows:
        per_group[row[comic_to_group]].append((row[rel], row["cnt"]))
    for gpk in group_pks:
        total = counts.get(gpk, 0)
        if not total:
            result[gpk][col] = []
            continue
        names = sorted(value for value, cnt in per_group.get(gpk, ()) if cnt == total)
        result[gpk][col] = names


_M2M_NAME_RELATIONS: MappingProxyType[str, str] = MappingProxyType(
    {
        "characters": "characters__name",
        "genres": "genres__name",
        "locations": "locations__name",
        "series_groups": "series_groups__name",
        "stories": "stories__name",
        "story_arcs": "story_arc_numbers__story_arc__name",
        "tags": "tags__name",
        "teams": "teams__name",
        "universes": "universes__name",
    }
)


def _compute_credits_intersection(
    group_pks: list[int],
    comic_to_group: str,
    counts: dict[int, int],
    result: dict[int, dict[str, Any]],
) -> None:
    """Credit intersection — by (person.name, role.name) tuple, formatted as "Person (Role)"."""
    rows = (
        Comic.objects.filter(**{f"{comic_to_group}__in": group_pks})
        .filter(credits__person__name__gt="")
        .values(
            comic_to_group,
            "credits__person__name",
            "credits__role__name",
        )
        .annotate(cnt=Count("pk", distinct=True))
    )
    per_group: dict[int, list[tuple[str, str | None, int]]] = defaultdict(list)
    for row in rows:
        per_group[row[comic_to_group]].append(
            (
                row["credits__person__name"],
                row["credits__role__name"],
                row["cnt"],
            )
        )
    for gpk in group_pks:
        total = counts.get(gpk, 0)
        if not total:
            result[gpk]["credits"] = []
            continue
        names = sorted(
            _format_credit(person, role)
            for person, role, cnt in per_group.get(gpk, ())
            if cnt == total
        )
        result[gpk]["credits"] = names


def _compute_identifiers_intersection(
    group_pks: list[int],
    comic_to_group: str,
    counts: dict[int, int],
    result: dict[int, dict[str, Any]],
) -> None:
    """Render identifier intersection as ``[source:]type:key`` per shared row."""
    rows = (
        Comic.objects.filter(**{f"{comic_to_group}__in": group_pks})
        .filter(Q(identifiers__id_type__gt="") | Q(identifiers__key__gt=""))
        .values(
            comic_to_group,
            "identifiers__source__name",
            "identifiers__id_type",
            "identifiers__key",
        )
        .annotate(cnt=Count("pk", distinct=True))
    )
    per_group: dict[int, list[tuple[str | None, str, str, int]]] = defaultdict(list)
    for row in rows:
        per_group[row[comic_to_group]].append(
            (
                row["identifiers__source__name"],
                row["identifiers__id_type"],
                row["identifiers__key"],
                row["cnt"],
            )
        )
    for gpk in group_pks:
        total = counts.get(gpk, 0)
        if not total:
            result[gpk]["identifiers"] = []
            continue
        names = sorted(
            _format_identifier(source, id_type, key)
            for source, id_type, key, cnt in per_group.get(gpk, ())
            if cnt == total
        )
        result[gpk]["identifiers"] = names
