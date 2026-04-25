"""OPDS Metadata Subqueries."""

import json
from collections.abc import Collection, Iterable, Sequence
from types import SimpleNamespace

from django.db.models import CharField, F, Value
from django.urls import reverse

from codex.models import (
    CreditPerson,
)
from codex.views.auth import GroupACLMixin
from codex.views.opds.const import OPDS_M2M_MODELS
from codex.views.opds.v1.const import TopRoutes

#################
# M2M QuerySets #
#################
# These M2M queries could techinally be added to the main query, but
# probably only if the desired output format was already known. Like a
# json object of model_name-pk, name for opds v1 and a json list of
# strings for opds v2. Its actually better from a code standpoint to
# not optimize the query like that, I think, and send the several
# querysets to the views and templates.


def get_credit_people(comic_pks: Sequence[int], roles: Iterable[str], *, exclude: bool):
    """Get credits that are not authors."""
    people = CreditPerson.objects.filter(
        credit__comic__in=comic_pks,
    )
    if exclude:
        people = people.exclude(credit__role__name__in=roles)
    else:
        people = people.filter(credit__role__name__in=roles)
    return people.distinct().only("name")


def get_m2m_objects(pks: Sequence[int]) -> dict:
    """Get Category labels."""
    cats = {}
    for model in OPDS_M2M_MODELS:
        table = model.__name__.lower()
        rel = GroupACLMixin.get_rel_prefix(model)
        comic_filter = {rel + "in": pks}
        qs = model.objects.filter(**comic_filter).only("name").order_by("name")
        cats[table] = qs

    return cats


def _credit_url_for(person_pk: int) -> str:
    """Build the OPDS v1 facet-style URL for a credit person."""
    filters = json.dumps({"credits": [person_pk]})
    return reverse(
        "opds:v1:feed", kwargs=dict(TopRoutes.SERIES), query={"filters": filters}
    )


def get_credit_people_by_comic(
    comic_pks: Collection[int],
    roles: Iterable[str],
    *,
    exclude: bool,
) -> dict[int, list]:
    """
    Per-comic mapping of distinct credit people for the given roles.

    The single-comic helper :func:`get_credit_people` fires one query
    per call. On a multi-comic acquisition feed (sub-plan 03 #1) the
    per-entry call multiplies into N queries; this helper collapses
    them to a single query with a Python-side partition.

    Returns ``{comic_pk: [SimpleNamespace(pk, name, url), ...]}`` —
    same shape the OPDS v1 entry template reads (``.name`` / ``.url``).
    """
    if not comic_pks:
        return {}
    qs = CreditPerson.objects.filter(credit__comic__in=comic_pks)
    if exclude:
        qs = qs.exclude(credit__role__name__in=roles)
    else:
        qs = qs.filter(credit__role__name__in=roles)
    rows = (
        qs.annotate(_comic_id=F("credit__comic"))
        .values("pk", "name", "_comic_id")
        .order_by("name")
    )
    by_pk: dict[int, list] = {pk: [] for pk in comic_pks}
    seen: dict[int, set[int]] = {pk: set() for pk in comic_pks}
    for row in rows:
        cid = row["_comic_id"]
        ppk = row["pk"]
        if cid not in by_pk or ppk in seen[cid]:
            continue
        seen[cid].add(ppk)
        person = SimpleNamespace(pk=ppk, name=row["name"], url=_credit_url_for(ppk))
        by_pk[cid].append(person)
    return by_pk


def get_m2m_objects_by_comic(
    comic_pks: Collection[int],
) -> dict[int, dict[str, list]]:
    """
    Per-comic mapping of M2M subject items grouped by model name.

    The single-comic helper :func:`get_m2m_objects` fires one query
    per ``OPDS_M2M_MODELS`` entry (7 by default) for a single comic.
    A multi-comic acquisition feed therefore fires ``7 * N`` queries
    in the worst case (sub-plan 03 #1). This helper UNIONs all seven
    M2M tables into one query keyed by ``(_comic_id, _kind)`` and
    partitions in Python.

    Returns ``{comic_pk: {model_name_lowercased: [SimpleNamespace(pk, name)]}}``
    — same shape the OPDS v1 entry template iterates over.
    """
    if not comic_pks or not OPDS_M2M_MODELS:
        return {}
    by_comic: dict[int, dict[str, list]] = {
        pk: {model.__name__.lower(): [] for model in OPDS_M2M_MODELS}
        for pk in comic_pks
    }
    queries = []
    for model in OPDS_M2M_MODELS:
        rel = GroupACLMixin.get_rel_prefix(model)
        kind = model.__name__.lower()
        q = (
            model.objects.filter(**{rel + "in": comic_pks})
            .annotate(
                _kind=Value(kind, output_field=CharField()),
                _comic_id=F(rel + "id"),
            )
            .values("pk", "name", "_kind", "_comic_id")
        )
        queries.append(q)
    rows = queries[0].union(*queries[1:], all=True).order_by("_kind", "name")
    seen: dict[tuple[int, str], set[int]] = {}
    for row in rows:
        cid = row["_comic_id"]
        kind = row["_kind"]
        ipk = row["pk"]
        bucket_key = (cid, kind)
        bucket_seen = seen.setdefault(bucket_key, set())
        if ipk in bucket_seen or cid not in by_comic:
            continue
        bucket_seen.add(ipk)
        by_comic[cid][kind].append(SimpleNamespace(pk=ipk, name=row["name"]))
    return by_comic
