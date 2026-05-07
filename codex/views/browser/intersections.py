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

from django.core.exceptions import FieldDoesNotExist
from django.db.models import Count, Q
from django.db.models.expressions import RawSQL

from codex.models import Comic
from codex.models.groups import Folder, Imprint, Publisher, Series, Volume
from codex.views.browser.columns import fk_name_columns, m2m_columns
from codex.views.const import MODEL_REL_MAP

# Comic FK column → group model. Used to correlate the intersection
# sort subquery to the outer group row. ``StoryArc`` traverses
# through ``StoryArcNumber`` so the subquery shape differs; deferred
# from this v1 group-row M2M sort.
_COMIC_GROUP_COL: MappingProxyType[type, str] = MappingProxyType(
    {
        Publisher: "publisher_id",
        Imprint: "imprint_id",
        Series: "series_id",
        Volume: "volume_id",
        Folder: "parent_folder_id",
    }
)


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


# ──────────────────────────────────────────────────────────────────────
# M2M-intersection sort key for group rows
#
# The order_value annotation for a group row sorting by an M2M column
# is the alphabetized concatenation of M2M values present in every
# child comic. Identical intersection sets render identical strings
# under SQLite's binary collation, so ORDER BY clusters equivalent
# rows together — the property the user already validated for the
# Comic-row M2M-sort experiment.
#
# We build the expression as RawSQL for two reasons:
#   1. SQLite's correlated-subquery + HAVING + GROUP_CONCAT pattern
#      with intra-row ORDER BY is straightforward in SQL but requires
#      ORM gymnastics (nested OuterRefs, .aggregate inside Subquery,
#      etc.) that obscure the intent.
#   2. Per-row execution against the outer group table is the most
#      efficient shape SQLite can deliver — see the perf note below.
#
# Performance: the subquery executes once per row in the outer
# queryset's ORDER BY phase. With indexes on the comic's group FK
# (codex_comic.<group>_id) and the through table's (comic_id, target_id)
# pair, each subquery scans only the relevant rows for that group.
# Profile-and-tune is the user's call; the SELECT is structurally
# minimal — one INNER JOIN chain through the M2M, one GROUP BY, one
# correlated COUNT for the HAVING clause.

# ``through_table_attr`` resolves to e.g. ``codex_comic_genres`` via
# Django's metadata; ``target_table_attr`` is the related model's
# ``_meta.db_table`` (``codex_genre``); ``m2m_id_col`` is the through
# table's FK column to the related model (``genre_id``). All three
# are looked up at runtime so we don't hardcode db_table names.
_SIMPLE_M2M_FIELDS = MappingProxyType(
    {
        "characters": "characters",
        "genres": "genres",
        "locations": "locations",
        "series_groups": "series_groups",
        "stories": "stories",
        "tags": "tags",
        "teams": "teams",
        # ``universes`` is *not* simple — its display includes the
        # ``designation`` field. Handled below.
    }
)


def _build_simple_m2m_intersection_sort_sql(
    group_model: type, column: str
) -> RawSQL | None:
    """
    Return a correlated-subquery RawSQL for the intersection sort key.

    Restricted to ``_SIMPLE_M2M_FIELDS`` and group models in
    ``_COMIC_GROUP_COL`` (StoryArc, credits, identifiers — deferred).
    Returns None when unsupported.
    """
    field_name = _SIMPLE_M2M_FIELDS.get(column)
    comic_group_col = _COMIC_GROUP_COL.get(group_model)
    if field_name is None or comic_group_col is None:
        return None
    field = Comic._meta.get_field(field_name)
    through = field.remote_field.through  # pyright: ignore[reportAttributeAccessIssue]
    through_table = through._meta.db_table
    m2m_id_col = f"{field.m2m_reverse_field_name()}_id"  # pyright: ignore[reportAttributeAccessIssue] # ty: ignore[unresolved-attribute]
    related_model = field.related_model
    if related_model is None:
        return None
    target_table = related_model._meta.db_table
    group_table = group_model._meta.db_table

    # Correlated subquery returning the alphabetized GROUP_CONCAT of
    # target ``name`` values whose comic-count for the outer group
    # matches the group's total comic count — the intersection set.
    # ```` (unit separator) is used as the join character so it
    # never collides with values in the names. NULL/empty target
    # names are filtered out so they can't fold into the sort key.
    # All identifiers spliced into ``sql`` come from Django metadata
    # (``_meta.db_table``, ``m2m_reverse_field_name()``); the column
    # whitelist (``_SIMPLE_M2M_FIELDS``) and group whitelist
    # (``_COMIC_GROUP_COL``) bound the inputs, so RawSQL is safe here.
    sql = f"""(
        SELECT COALESCE(GROUP_CONCAT(name, X'1F'), '')
        FROM (
            SELECT t.name AS name
            FROM {target_table} t
            INNER JOIN {through_table} th ON th.{m2m_id_col} = t.id
            INNER JOIN codex_comic c ON c.id = th.comic_id
            WHERE c.{comic_group_col} = {group_table}.id
              AND t.name IS NOT NULL
              AND t.name != ''
            GROUP BY t.id, t.name
            HAVING COUNT(DISTINCT c.id) = (
                SELECT COUNT(*) FROM codex_comic
                WHERE {comic_group_col} = {group_table}.id
            )
            ORDER BY t.name
        ) AS isect
    )"""  # noqa: S608
    return RawSQL(sql, [])  # noqa: S611


def _wrap_intersection_sort(
    inner_select: str, comic_group_col: str, group_table: str
) -> str:
    """
    Wrap a per-row display-string SELECT with the standard intersection envelope.

    ``inner_select`` is the SELECT body that produces a ``display_name``
    column for each (target, comic) row. The envelope filters by group
    correlation, groups by the target's identity, applies the
    intersection HAVING, and concatenates per-group with the same
    X'1F' separator the simple variant uses.

    All identifiers spliced in (``comic_group_col``, ``group_table``,
    plus the inner_select body) come from caller-side whitelists, not
    user input — caller-level S608 noqa applies.
    """
    return f"""(
        SELECT COALESCE(GROUP_CONCAT(display_name, X'1F'), '')
        FROM (
            {inner_select}
            WHERE c.{comic_group_col} = {group_table}.id
              AND display_name IS NOT NULL
              AND display_name != ''
            GROUP BY target_id
            HAVING COUNT(DISTINCT c.id) = (
                SELECT COUNT(*) FROM codex_comic
                WHERE {comic_group_col} = {group_table}.id
            )
            ORDER BY display_name
        ) AS isect
    )"""  # noqa: S608


def _build_universes_intersection_sort_sql(group_model: type) -> RawSQL | None:
    """Universes display as ``name:designation`` (or just ``name`` when blank)."""
    comic_group_col = _COMIC_GROUP_COL.get(group_model)
    if comic_group_col is None:
        return None
    group_table = group_model._meta.db_table
    inner = """
            SELECT
                u.id AS target_id,
                CASE
                    WHEN u.designation IS NULL OR u.designation = ''
                        THEN u.name
                    ELSE u.name || ':' || u.designation
                END AS display_name
            FROM codex_universe u
            INNER JOIN codex_comic_universes th ON th.universe_id = u.id
            INNER JOIN codex_comic c ON c.id = th.comic_id
    """
    sql = _wrap_intersection_sort(inner, comic_group_col, group_table)
    return RawSQL(sql, [])  # noqa: S611


def _build_credits_intersection_sort_sql(group_model: type) -> RawSQL | None:
    """Credits display as ``Person (Role)`` (or ``Person`` when role is null)."""
    comic_group_col = _COMIC_GROUP_COL.get(group_model)
    if comic_group_col is None:
        return None
    group_table = group_model._meta.db_table
    # Two comics share a Credit only when they reference the same row;
    # ``unique_together = ("person", "role")`` on Credit makes the
    # (person, role) pair the de-facto identity, so grouping by
    # ``credit.id`` is equivalent to grouping by the pair.
    inner = """
            SELECT
                cred.id AS target_id,
                CASE
                    WHEN cr.id IS NULL THEN cp.name
                    ELSE cp.name || ' (' || cr.name || ')'
                END AS display_name
            FROM codex_credit cred
            INNER JOIN codex_creditperson cp ON cp.id = cred.person_id
            LEFT JOIN codex_creditrole cr ON cr.id = cred.role_id
            INNER JOIN codex_comic_credits th ON th.credit_id = cred.id
            INNER JOIN codex_comic c ON c.id = th.comic_id
    """
    sql = _wrap_intersection_sort(inner, comic_group_col, group_table)
    return RawSQL(sql, [])  # noqa: S611


def _build_identifiers_intersection_sort_sql(group_model: type) -> RawSQL | None:
    """Render identifiers intersection as ``[source:]type:key`` per shared row."""
    comic_group_col = _COMIC_GROUP_COL.get(group_model)
    if comic_group_col is None:
        return None
    group_table = group_model._meta.db_table
    inner = """
            SELECT
                idn.id AS target_id,
                CASE
                    WHEN src.id IS NULL THEN idn.id_type || ':' || idn.key
                    ELSE src.name || ':' || idn.id_type || ':' || idn.key
                END AS display_name
            FROM codex_identifier idn
            LEFT JOIN codex_identifiersource src ON src.id = idn.source_id
            INNER JOIN codex_comic_identifiers th ON th.identifier_id = idn.id
            INNER JOIN codex_comic c ON c.id = th.comic_id
    """
    sql = _wrap_intersection_sort(inner, comic_group_col, group_table)
    return RawSQL(sql, [])  # noqa: S611


def _build_story_arcs_intersection_sort_sql(group_model: type) -> RawSQL | None:
    """Story arcs go through ``StoryArcNumber``; group by the parent ``StoryArc``."""
    comic_group_col = _COMIC_GROUP_COL.get(group_model)
    if comic_group_col is None:
        return None
    group_table = group_model._meta.db_table
    # Comic.story_arc_numbers → StoryArcNumber → story_arc → StoryArc.
    # We want intersection by StoryArc (not StoryArcNumber): a story
    # arc is "shared" if every comic has at least one StoryArcNumber
    # pointing to it, regardless of issue number.
    inner = """
            SELECT
                sa.id AS target_id,
                sa.name AS display_name
            FROM codex_storyarc sa
            INNER JOIN codex_storyarcnumber san ON san.story_arc_id = sa.id
            INNER JOIN codex_comic_story_arc_numbers th ON th.storyarcnumber_id = san.id
            INNER JOIN codex_comic c ON c.id = th.comic_id
    """
    sql = _wrap_intersection_sort(inner, comic_group_col, group_table)
    return RawSQL(sql, [])  # noqa: S611


def scalar_intersection_sort_expr(
    group_model: type, column: str
) -> RawSQL | None:
    """
    Build a sort-key RawSQL for scalar / FK-name group-row sort.

    The group-row *display* uses intersection (``_compute_scalar_intersection``):
    a value renders only when every child comic in the group shares it
    (same non-NULL value, no missing children). The default
    ``Min`` / ``Avg`` / ``Sum`` aggregates used by ``annotate_order_value``
    don't agree with that — a series whose children mostly lack a year
    but one happens to be 2024 sorts as if year=2024 yet displays
    blank. Mirroring the intersection rule in SQL keeps display and
    sort consistent: the ORDER BY value is the per-group value when
    every child agrees, NULL otherwise. NULLs follow SQLite's default
    sort position (smallest in ASC, last in DESC).

    Returns None when the column or group model isn't supported;
    callers fall back to the previous aggregate path so we don't
    silently break an existing sort if the registry adds a new field
    we haven't wired here yet.
    """
    path = _SCALAR_FIELD_PATHS.get(column)
    comic_group_col = _COMIC_GROUP_COL.get(group_model)
    if path is None or comic_group_col is None:
        return None
    group_table = group_model._meta.db_table

    if "__" not in path:
        # Direct Comic field — year, page_count, size, file_type, …
        # All identifiers spliced in (``path``, ``comic_group_col``,
        # ``group_table``) come from caller-side whitelists; RawSQL
        # is safe — same justification as ``_build_simple_m2m_…``.
        col = f"c.{path}"
        sql = f"""(
            SELECT
                CASE
                    WHEN COUNT({col}) = (
                        SELECT COUNT(*) FROM codex_comic
                        WHERE {comic_group_col} = {group_table}.id
                    )
                      AND MIN({col}) = MAX({col})
                    THEN MIN({col})
                    ELSE NULL
                END
            FROM codex_comic c
            WHERE c.{comic_group_col} = {group_table}.id
        )"""  # noqa: S608
        return RawSQL(sql, [])  # noqa: S611

    # FK-to-name field — tagger__name, country__name, age_rating__name, …
    fk_attr, target_field = path.split("__", 1)
    try:
        fk_field = Comic._meta.get_field(fk_attr)
    except FieldDoesNotExist:
        return None
    related_model = fk_field.related_model
    if related_model is None:
        return None
    fk_col = fk_field.column  # e.g. ``tagger_id``
    target_table = related_model._meta.db_table
    target_col = f"t.{target_field}"
    sql = f"""(
        SELECT
            CASE
                WHEN COUNT({target_col}) = (
                    SELECT COUNT(*) FROM codex_comic
                    WHERE {comic_group_col} = {group_table}.id
                )
                  AND MIN({target_col}) = MAX({target_col})
                THEN MIN({target_col})
                ELSE NULL
            END
        FROM codex_comic c
        LEFT JOIN {target_table} t ON c.{fk_col} = t.id
        WHERE c.{comic_group_col} = {group_table}.id
    )"""  # noqa: S608
    return RawSQL(sql, [])  # noqa: S611


def m2m_intersection_sort_expr(group_model: type, column: str) -> RawSQL | None:
    """
    Build a sort-key RawSQL for the given (group_model, M2M column).

    Public entry point. Returns None when the combination isn't
    supported; callers fall back to sort_name.
    """
    if column in _SIMPLE_M2M_FIELDS:
        return _build_simple_m2m_intersection_sort_sql(group_model, column)
    if column == "universes":
        return _build_universes_intersection_sort_sql(group_model)
    if column == "credits":
        return _build_credits_intersection_sort_sql(group_model)
    if column == "identifiers":
        return _build_identifiers_intersection_sort_sql(group_model)
    if column == "story_arcs":
        return _build_story_arcs_intersection_sort_sql(group_model)
    return None


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
