"""
Which of the requesting user's shelves a browser row or metadata selection is on.

Membership is *effective*: a comic is on a shelf when it sits there itself or
through any parent -- its publisher, imprint, series or volume, any ancestor
folder, or any reading list it is in. :func:`effective_comic_q` builds that rule;
the shelves browser filter (``BrowserFilterView.get_shelf_filter``) uses it
too, so a row that lists a shelf is a row the shelf filter returns. A collection row, or a metadata
selection, is on a shelf when every live comic the user can see under it is:
the intersection rule every other collection-row tag column uses
(:mod:`codex.views.browser.intersections`). The table view's sortable
``shelved`` flag (:func:`annotate_shelved`) follows the same rule, so a row
sorts as shelved exactly when its Shelves cell lists a shelf.

Only shelf pks leave this module. Shelf names are free text the user owns;
the frontend resolves them from its own shelves store, which also keeps a
renamed or deleted shelf current without a refetch.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final, override

from cachalot.api import cachalot_disabled
from django.db.models import (
    BooleanField,
    Count,
    Exists,
    ExpressionWrapper,
    OuterRef,
    Q,
    QuerySet,
    Value,
)

from codex.collection import Collection
from codex.models import Comic, ReadingListEntry
from codex.models.query import GroupByQuerySet
from codex.models.shelf import SHELF_MODEL_COLLECTIONS, ShelfItem
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

# Folders and reading lists are many-to-many on Comic (every ancestor folder,
# every list), so their clauses go through the through table as a ``pk__in``
# subquery instead of a join. That keeps each shelf's clause join-free, which
# is what makes it safe as an aggregate ``filter=`` on a queryset that is
# itself grouped through ``folders`` or the list relation: a join there would
# be reused by the grouping and only ever see the row's own folder or list.
# Each is ``(through model, target lookup, extra filter)``: a hidden entry
# is no part of its list, so it puts no comic on a shelf.
_THROUGH_BY_COLLECTION: Final[
    MappingProxyType[str, tuple[Any, str, Mapping[str, Any]]]
] = MappingProxyType(
    {
        Collection.FOLDER.value: (
            Comic.folders.through,
            "folder_id__in",
            MappingProxyType({}),
        ),
        Collection.ARC.value: (
            ReadingListEntry,
            "reading_list_id__in",
            MappingProxyType({"ignored": False}),
        ),
    }
)
SHELF_COMIC_COLLECTIONS: Final = frozenset(
    (*_COMIC_FIELD_BY_COLLECTION, *_THROUGH_BY_COLLECTION)
)

_TOTAL_ALIAS: Final = "_shelf_comic_total"
_SOME_ALIAS: Final = "_shelved_some"
_SHELVED_FALSE: Final = Value(value=False, output_field=BooleanField())


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


def shelf_targets(shelf_pks: Iterable[int], collection: str) -> QuerySet:
    """Return the target pks the shelves hold in one collection, as a subquery."""
    # ``values()`` returns a QuerySet at runtime; the stubs' ValuesQuerySet
    # isn't assignable to it.
    return ShelfItem.objects.filter(  # pyright: ignore[reportReturnType]
        shelf_id__in=tuple(shelf_pks), collection=collection
    ).values("target_id")


def effective_comic_q(
    shelf_pks: Iterable[int], collections: Iterable[str], rel: str = ""
) -> Q:
    """
    Comics on any of ``shelf_pks`` directly or through a parent.

    ``collections`` are the collections the shelves hold items in; a clause
    is built for each. ``rel`` is the path from the filtered model to its
    comics (``""`` for Comic, ``"comic__"`` for a collection). Folders and
    reading lists go through ``pk__in`` subqueries of their through tables, so
    the Q adds no join to the filtered query and cannot multiply its sums.
    """
    shelf_pks = tuple(shelf_pks)
    q = Q()
    for collection in sorted(collections):
        targets = shelf_targets(shelf_pks, collection)
        if field := _COMIC_FIELD_BY_COLLECTION.get(collection):
            q |= Q(**{f"{rel}{field}__in": targets})
        elif through_lookup := _THROUGH_BY_COLLECTION.get(collection):
            through, lookup, extra = through_lookup
            comic_ids = through.objects.filter(**{lookup: targets}, **extra).values(
                "comic_id"
            )
            q |= Q(**{f"{rel}pk__in": comic_ids})
    return q


class _RowFlag(ExpressionWrapper):
    """
    A per-row boolean of correlated subqueries, kept out of GROUP BY.

    Django groups an aggregated queryset by every non-aggregate expression
    it selects, so the whole flag landed in GROUP BY and SQLite evaluated
    its subqueries once per *pre-aggregation joined row*: the folders
    browse, fanned out to every descendant comic, took 22 s cold. The
    flag's only outer reference is the row's pk, already in the GROUP BY,
    so it adds no grouping (as ``intersections._IntersectionSortRawSQL``).
    """

    @override
    def get_group_by_cols(self) -> list:
        return []


def _every_alias(shelf_pk: int) -> str:
    return f"_shelved_every_{shelf_pk}"


def _collection_pk_flags(
    shelf_collections: Mapping[int, frozenset[str]], acl: "ComicACL", rel: str
) -> dict[str, Exists]:
    """
    Flag each collection pk: has it a comic, and does each shelf hold them all.

    ``_SOME_ALIAS`` is whether the pk has a live comic ``acl`` lets the user
    see, ``_every_alias(shelf_pk)`` whether that shelf holds every one.
    """
    comics = Comic.objects.filter(LIVE_COMIC, acl.q(Comic), **{rel: OuterRef("pk")})
    flags = {_SOME_ALIAS: Exists(comics)}
    for shelf_pk, collections in shelf_collections.items():
        off_shelf = comics.exclude(effective_comic_q((shelf_pk,), collections))
        flags[_every_alias(shelf_pk)] = ~Exists(off_shelf)
    return flags


def _correlated_row_flag(qs: QuerySet, flags: Mapping[str, Exists]) -> QuerySet:
    """Annotate a row that stands for one pk from its own flags."""
    on_a_shelf = Q()
    for alias in flags:
        if alias != _SOME_ALIAS:
            on_a_shelf |= Q(**{alias: True})
    shelved = _RowFlag(Q(**{_SOME_ALIAS: True}) & on_a_shelf, BooleanField())
    return qs.alias(**flags).annotate(shelved=shelved)


def _merged_row_is_shelved(member_flags: Sequence[Sequence[bool]]) -> bool:
    """
    Whether a row's pks, by their flags, share a shelf.

    Some pk has a comic, and one shelf holds every comic of every pk: the
    sum rule ``_shared_shelf_pks`` applies to a merged row's counts.
    """
    if not any(flags[0] for flags in member_flags):
        return False
    num_flags = len(member_flags[0])
    return any(
        all(flags[index] for flags in member_flags) for index in range(1, num_flags)
    )


def _merged_row_flag(
    qs: GroupByQuerySet, group_fields: Sequence[str], flags: Mapping[str, Exists]
) -> QuerySet:
    """
    Annotate rows grouped by name, each of which may stand for several pks.

    A grouped query selects one arbitrary pk per row, so a correlated flag
    would judge a merged row by that pk alone. Instead the flags are read
    per pk over the ungrouped browse filter, folded per row in Python, and
    the rows found shelved are spelled as a pk list: whichever pk a row
    selects is in it. A literal list has no subquery for cachalot to miss;
    the per-pk query it comes from is an ordinary ``Exists`` annotation.
    """
    ungrouped = qs.group_by()
    per_pk = (
        qs.model.objects.filter(pk__in=ungrouped.values("pk"))
        .annotate(**flags)
        .values_list("pk", *group_fields, *flags)
    )
    width = len(group_fields)
    rows: dict[tuple, list[tuple[int, Sequence[bool]]]] = defaultdict(list)
    for pk, *values in per_pk:
        rows[tuple(values[:width])].append((pk, values[width:]))
    shelved_pks = [
        pk
        for members in rows.values()
        if _merged_row_is_shelved([member_flags for _, member_flags in members])
        for pk, _ in members
    ]
    if not shelved_pks:
        return qs.annotate(shelved=_SHELVED_FALSE)
    return qs.annotate(shelved=_RowFlag(Q(pk__in=shelved_pks), BooleanField()))


def annotate_shelved(qs: QuerySet, user, acl: "ComicACL") -> QuerySet:
    """
    Annotate ``shelved``: whether the row's Shelves cell lists any shelf.

    The table view's sortable flag, by the cell's rule
    (:func:`page_row_shelves`): a comic is shelved when it is on one of
    ``user``'s shelves itself or through a parent; a collection row when
    some shelf holds every live comic ``acl`` lets the user see under it
    (under every pk it stands for), and it has at least one.

    Every subquery is an ``Exists`` annotation or alias, never a condition
    nested in ``When``/``ExpressionWrapper``, whose tables cachalot can't
    see: the flag must not be served stale after a shelf change.

    A model that can't be shelved is returned as is. Anonymous sessions and
    users with nothing shelved get a constant False.
    """
    model = qs.model
    if model not in SHELF_MODEL_COLLECTIONS:
        return qs
    shelf_collections = _user_shelf_collections(user)
    rel = "pk" if model is Comic else intersection_relation(model)
    if not shelf_collections or not rel:
        return qs.annotate(shelved=_SHELVED_FALSE)
    if model is Comic:
        collections = frozenset().union(*shelf_collections.values())
        on_any = effective_comic_q(tuple(shelf_collections), collections)
        shelved = Exists(Comic.objects.filter(on_any, pk=OuterRef("pk")))
        return qs.annotate(shelved=shelved)
    flags = _collection_pk_flags(shelf_collections, acl, rel)
    group_fields = getattr(qs.query, "force_group_by_fields", ())
    if group_fields and isinstance(qs, GroupByQuerySet):
        return _merged_row_flag(qs, group_fields, flags)
    return _correlated_row_flag(qs, flags)


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
            "pk", distinct=True, filter=effective_comic_q((shelf_pk,), collections)
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
