"""
Which of the requesting user's shelves a browser row or metadata selection is on.

Membership is *effective*: a comic is on a shelf when it sits there itself or
through any parent -- its publisher, imprint, series or volume, any ancestor
folder, or any reading list it is in. That is the rule the shelves browser filter
already applies (``BrowserFilterView.get_shelf_filter``), so a row that lists
a shelf is a row the shelf filter returns. A collection row, or a metadata
selection, is on a shelf when every live comic the user can see under it is:
the intersection rule every other collection-row tag column uses
(:mod:`codex.views.browser.intersections`).

Only shelf pks leave this module. Shelf names are free text the user owns;
the frontend resolves them from its own shelves store, which also keeps a
renamed or deleted shelf current without a refetch.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from cachalot.api import cachalot_disabled
from django.db.models import Count, Q, QuerySet

from codex.collection import Collection
from codex.models import Comic, ReadingListEntry
from codex.models.shelf import ShelfItem
from codex.views.browser.intersections import (
    LIVE_COMIC,
    collection_row_pks,
    intersection_relation,
)

if TYPE_CHECKING:
    from codex.views.auth import ComicACL

# A shelved target of these collections puts a comic on the shelf when the
# comic's own field holds the target's pk.
_COMIC_FIELD_BY_COLLECTION: Final[MappingProxyType[str, str]] = MappingProxyType(
    {
        Collection.COMIC.value: "pk",
        Collection.PUBLISHER.value: "publisher_id",
        Collection.IMPRINT.value: "imprint_id",
        Collection.SERIES.value: "series_id",
        Collection.VOLUME.value: "volume_id",
    }
)

# Folders and story arcs are many-to-many on Comic (every ancestor folder, every
# arc), so their clauses go through the through table as a ``pk__in``
# subquery instead of a join. That keeps each shelf's clause join-free, which
# is what makes it safe as an aggregate ``filter=`` on a queryset that is
# itself grouped through ``folders`` or the arc relation: a join there would
# be reused by the grouping and only ever see the row's own folder or arc.
_THROUGH_BY_COLLECTION: Final[MappingProxyType[str, tuple[Any, str]]] = (
    MappingProxyType(
        {
            Collection.FOLDER.value: (Comic.folders.through, "folder_id__in"),
            Collection.ARC.value: (ReadingListEntry, "reading_list_id__in"),
        }
    )
)
SHELF_COMIC_COLLECTIONS: Final = frozenset(
    (*_COMIC_FIELD_BY_COLLECTION, *_THROUGH_BY_COLLECTION)
)

_TOTAL_ALIAS: Final = "_shelf_comic_total"


def _shelf_alias(shelf_pk: int) -> str:
    return f"_shelf_{shelf_pk}"


def _user_shelf_collections(user) -> dict[int, frozenset[str]]:
    """
    Map each of ``user``'s non-empty shelves to the collections it holds.

    Ordered by shelf name so every pk list built from it comes out in the
    order the shelf menu lists the shelves. Empty for anonymous sessions,
    which own no shelves, and for users with nothing shelved -- callers
    short-circuit on it before touching any comic.
    """
    if not user or not user.is_authenticated:
        return {}
    rows = (
        ShelfItem.objects.filter(shelf__user=user)
        .order_by("shelf__name", "shelf_id")
        .values_list("shelf_id", "collection")
        .distinct()
    )
    collections: dict[int, set[str]] = defaultdict(set)
    for shelf_pk, collection in rows:
        collections[shelf_pk].add(collection)
    return {shelf_pk: frozenset(codes) for shelf_pk, codes in collections.items()}


def _effective_comic_q(shelf_pk: int, collections: Iterable[str]) -> Q:
    """Comics on ``shelf_pk`` directly or through a parent, over its collections."""
    q = Q()
    for collection in sorted(collections):
        targets = ShelfItem.objects.filter(
            shelf_id=shelf_pk, collection=collection
        ).values("target_id")
        if field := _COMIC_FIELD_BY_COLLECTION.get(collection):
            q |= Q(**{f"{field}__in": targets})
        elif through_lookup := _THROUGH_BY_COLLECTION.get(collection):
            through, lookup = through_lookup
            comic_ids = through.objects.filter(**{lookup: targets}).values("comic_id")
            q |= Q(pk__in=comic_ids)
    return q


def _count_annotations(shelf_collections: Mapping[int, frozenset[str]]) -> dict:
    """
    Build a comic total plus one effective-membership count per shelf.

    Queries carrying these must run under ``cachalot_disabled()``. cachalot
    finds a query's tables in its joins, WHERE and annotation subqueries,
    but not in a subquery nested in an aggregate's ``filter=``, so it would
    not tie these counts to ``codex_shelfitem`` and would serve them stale
    after a shelf change. They are cheap and per user; skip the cache.
    """
    annotations: dict[str, Count] = {_TOTAL_ALIAS: Count("pk", distinct=True)}
    for shelf_pk, collections in shelf_collections.items():
        annotations[_shelf_alias(shelf_pk)] = Count(
            "pk", distinct=True, filter=_effective_comic_q(shelf_pk, collections)
        )
    return annotations


def _shared_shelf_pks(
    shelf_pks: Iterable[int], count_rows: Sequence[Mapping[str, int]]
) -> list[int]:
    """
    Shelves holding every comic the count rows cover.

    A row merging several pks (series grouped by name) sums its pks' rows.
    Their comics are disjoint for the FK relations; for story arcs a comic
    in two merged arcs is counted twice on both sides of the comparison,
    so the equality still means "every comic".
    """
    total = sum(row[_TOTAL_ALIAS] for row in count_rows)
    if not total:
        return []
    return [
        shelf_pk
        for shelf_pk in shelf_pks
        if sum(row[_shelf_alias(shelf_pk)] for row in count_rows) == total
    ]


def _group_counts(
    shelf_collections: Mapping[int, frozenset[str]],
    acl: "ComicACL",
    rel: str,
    pks: Iterable[int],
) -> dict[int, dict[str, int]]:
    """
    Count, per ``rel`` pk, its live visible comics and those on each shelf.

    One grouped query for the whole page. The total and the per-shelf counts
    come from the same live-and-ACL filtered rows, the numerator and
    denominator rule the tag intersections follow.
    """
    rows = (
        Comic.objects.filter(LIVE_COMIC, acl.q(Comic), **{f"{rel}__in": pks})
        .values(rel)
        .annotate(**_count_annotations(shelf_collections))
    )
    with cachalot_disabled():
        return {row[rel]: row for row in rows}


def _collection_row_shelves(
    shelf_collections: Mapping[int, frozenset[str]],
    acl: "ComicACL",
    collection_qs: QuerySet,
) -> dict[int, list[int]]:
    rel = intersection_relation(collection_qs.model)
    if not rel:
        return {}
    row_ids = collection_row_pks(collection_qs)
    all_ids = {pk for ids in row_ids.values() for pk in ids}
    if not all_ids:
        return {}
    counts = _group_counts(shelf_collections, acl, rel, all_ids)
    return {
        row_pk: _shared_shelf_pks(
            shelf_collections, [counts[pk] for pk in ids if pk in counts]
        )
        for row_pk, ids in row_ids.items()
    }


def _book_row_shelves(
    shelf_collections: Mapping[int, frozenset[str]],
    acl: "ComicACL",
    book_qs: QuerySet,
) -> dict[int, list[int]]:
    pks = [book.pk for book in book_qs]
    if not pks:
        return {}
    counts = _group_counts(shelf_collections, acl, "pk", pks)
    return {
        pk: _shared_shelf_pks(shelf_collections, [counts[pk]] if pk in counts else [])
        for pk in pks
    }


def page_row_shelves(
    user, acl: "ComicACL", collection_qs: QuerySet | None, book_qs: QuerySet | None
) -> dict[str, dict[int, list[int]]]:
    """
    Return the shelf pks of every row on a table-view page.

    ``{"collections": {row_pk: [shelf_pk, ...]}, "books": {comic_pk: [...]}}``,
    keyed apart because folder view lists folders and comics on one page and
    their pks collide. Both querysets are the paginated page; iterating them
    here primes the result cache the serializer reads from.
    """
    result: dict[str, dict[int, list[int]]] = {"collections": {}, "books": {}}
    shelf_collections = _user_shelf_collections(user)
    if not shelf_collections:
        return result
    if collection_qs is not None and collection_qs.model is not Comic:
        result["collections"] = _collection_row_shelves(
            shelf_collections, acl, collection_qs
        )
    if book_qs is not None:
        result["books"] = _book_row_shelves(shelf_collections, acl, book_qs)
    return result


def selection_shelves(user, comic_pks: QuerySet, num_comics: int) -> list[int]:
    """
    Return the shelves every comic of a metadata selection is on.

    ``comic_pks`` is the selection's already-filtered comic pk subquery and
    ``num_comics`` its size, both from ``MetadataQueryIntersectionsView``.
    """
    shelf_collections = _user_shelf_collections(user)
    if not shelf_collections or not num_comics:
        return []
    with cachalot_disabled():
        counts = Comic.objects.filter(pk__in=comic_pks).aggregate(
            **_count_annotations(shelf_collections)
        )
    return _shared_shelf_pks(shelf_collections, [counts])
