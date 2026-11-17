"""Browser Filters."""

from functools import cached_property
from typing import Final

from django.db.models import Exists, OuterRef
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q

from codex.collection import Collection
from codex.models import Comic, ReadingList, ReadingListSource
from codex.models.readinglist import ReadingListSourceKind
from codex.models.shelf import SHELF_MODEL_COLLECTIONS, Shelf, ShelfItem
from codex.views.browser.filters.bookmark import BrowserFilterBookmarkView
from codex.views.const import FOLDER_COLLECTION, STORY_ARC_COLLECTION

# Active filter keys whose ORM rel crosses an m2m or m2m-through relation
# on Comic. Field-list mirrors ``codex.views.browser.const.BROWSER_FILTER_KEYS``
# minus the local-column / FK keys (year, decade, country, language,
# community_rating, monochrome, original_format, file_type, reading_direction,
# tagger, age_rating_metron, age_rating_tagged, series_end_year,
# series_start_year, series_status).
_M2M_FILTER_KEYS: Final[frozenset[str]] = frozenset(
    {
        "characters",
        "credits",
        "genres",
        "identifier_source",
        "locations",
        "reprints",
        "series_groups",
        "stories",
        "story_arcs",
        "tags",
        "teams",
        "universes",
    }
)
# TARGETs whose folder-group filter resolves to ``folders`` (m2m) or
# ``comic__folders`` (download) rather than ``parent_folder`` (FK).
# Mirrors the branches in :meth:`CollectionFilterView._get_rel_for_pks`.
_M2M_FOLDER_GROUP_TARGETS: Final[frozenset[str]] = frozenset(
    {"cover", "choices", "bookmark", "download", "force_update"}
)

# Collection codes whose transitive shelf clauses introduce m2m JOINs on
# Comic (``folders`` and ``reading_list_entries__reading_list``). When the
# selected shelves hold nothing under either code the filter Q has no m2m
# clauses and Comic queries don't need ``.distinct()``.
_SHELF_M2M_COLLECTION_CODES: Final[frozenset[str]] = frozenset(
    {Collection.FOLDER.value, Collection.ARC.value}
)

# Collection code → comic-side ORM field used to "transitively" match a
# row in that collection. ``folders`` is the m2m of every ancestor folder
# and ``reading_list_entries__reading_list`` every list a comic is in, so a
# single shelved folder or list lights up every comic in it.
_SHELF_COLLECTION_COMIC_REL: Final[dict[str, str]] = {
    Collection.COMIC.value: "pk",
    Collection.PUBLISHER.value: "publisher_id",
    Collection.IMPRINT.value: "imprint_id",
    Collection.SERIES.value: "series_id",
    Collection.VOLUME.value: "volume_id",
    Collection.FOLDER.value: "folders",
    Collection.ARC.value: "reading_list_entries__reading_list",
}


class BrowserFilterView(BrowserFilterBookmarkView):
    """Browser Filters."""

    def force_inner_joins(self, qs):
        """Force INNER JOINS to filter empty collections."""
        demote_tables = {"codex_library"}
        if qs.model is not Comic:
            demote_tables.add("codex_comic")
        if qs.model is ReadingList:
            # List browse reaches Comic through one more LEFT-JOINed
            # table, the entries: the collection relation itself, so
            # NULL-extended rows are exactly the empty lists this method
            # exists to drop. Demoting it lets SQLite start the plan from
            # the FTS/comic side instead of a list-side scan, as it did
            # for story arcs (an arc search browse measured 150s vs 36ms
            # per query). Scoped to ReadingList: elsewhere the table could
            # join as an annotation, where demotion would drop rows.
            demote_tables.add("codex_readinglistentry")
        if self.fts_mode:
            # Forcing INNER JOINS required to make fts5 work
            demote_tables.add("codex_comicfts")
        return qs.demote_joins(demote_tables)

    @cached_property
    def _shelf_filter_requested(self) -> bool:
        """Whether this request filters by shelf at all."""
        return bool(self.params.get("filters", {}).get("shelves"))

    @cached_property
    def _active_shelf_pks(self) -> tuple[int, ...]:
        """
        Return the requested shelves that belong to the requesting user.

        Shelves are private: a pk the user does not own (another user's
        shelf, a deleted shelf, a stale saved view) is dropped here, once
        per request, so it can never widen what the filter matches.
        Anonymous sessions own no shelves.
        """
        if not self._shelf_filter_requested:
            return ()
        user = self.request.user
        if not user or not user.is_authenticated:
            return ()
        requested = [
            int(pk)
            for pk in self.params["filters"]["shelves"]
            if isinstance(pk, int) or (isinstance(pk, str) and pk.isdigit())
        ]
        if not requested:
            return ()
        return tuple(
            Shelf.objects.filter(user=user, pk__in=requested)
            .order_by("pk")
            .values_list("pk", flat=True)
        )

    @cached_property
    def _active_shelf_collection_codes(self) -> frozenset[str]:
        """
        Return the collections the selected shelves hold at least one item in.

        One ``DISTINCT`` query per request, cached. Used by
        ``get_shelf_filter`` to skip OR clauses for empty collections
        (which would otherwise force m2m JOINs through ``folders`` and
        ``story_arc_numbers`` on every shelf-filtered request) and
        by ``comic_filter_uses_m2m`` to gate ``.distinct()``.
        """
        shelf_pks = self._active_shelf_pks
        if not shelf_pks:
            return frozenset()
        return frozenset(
            ShelfItem.objects.filter(shelf_id__in=shelf_pks)
            .values_list("collection", flat=True)
            .distinct()
        )

    @cached_property
    def comic_filter_uses_m2m(self) -> bool:
        """
        Return True if the filter pipeline forces an m2m join on Comic.

        Drives whether ``.distinct()`` and the ``search_score`` ``group_by("id")``
        clause need to fire. Non-Comic queries always need them because the
        ACL filter alone traverses ``comic__`` (one-to-many); for Comic
        queries we can skip both unless a real m2m relation joins in.
        """
        collection = self.kwargs.get("collection")
        pks = self.kwargs.get("pks")
        if pks and 0 not in pks:
            if collection == STORY_ARC_COLLECTION:
                # ``reading_list_entries`` is one-to-many on Comic, and a
                # comic may sit in a list more than once.
                return True
            if (
                collection == FOLDER_COLLECTION
                and self.TARGET in _M2M_FOLDER_GROUP_TARGETS
            ):
                # ``folders`` / ``comic__folders`` m2m on these targets.
                return True
        filters = self.params.get("filters") or {}
        if self._active_shelf_collection_codes & _SHELF_M2M_COLLECTION_CODES:
            # The transitive shelf Q only introduces m2m clauses for
            # collections the selected shelves actually hold items in.
            # With no shelved folders / arcs the Q stays on direct fields
            # and Comic queries don't need ``.distinct()``.
            return True
        return any(filters.get(k) for k in _M2M_FILTER_KEYS)

    @cached_property
    def _shelf_subqueries(self):
        """Per-collection shelved-id subqueries, built once per request."""
        shelf_pks = self._active_shelf_pks
        return {
            code: ShelfItem.objects.filter(
                shelf_id__in=shelf_pks, collection=code
            ).values("target_id")
            for code in self._active_shelf_collection_codes
        }

    def get_shelf_filter(self, model) -> Q:
        """
        Return a transitive Q for the shelves filter, or ``Q()``.

        Selecting several shelves matches items on any of them, the same
        OR-within-a-filter rule the tag filters use.

        Hierarchical: a row passes if itself, an ancestor, or a
        descendant in the comic chain is on a selected shelf. That keeps
        the filter behaving like a "navigation tree of shelved items" —
        shelving a Publisher narrows to its full subtree (so the user
        can drill down to the comic), and shelving a Comic keeps every
        ancestor (Publisher → Series → Volume → Comic) reachable.

        Each OR clause traces ``rel_prefix + comic_field`` to a
        per-collection shelved-id subquery, but only for collections the
        selected shelves actually hold items in (see
        :attr:`_active_shelf_collection_codes`). That keeps the
        ``folders`` / ``reading_list_entries__reading_list`` JOINs out of
        the SQL when no folders / lists are shelved — typically the
        common case. ``folders`` is the m2m of every ancestor folder
        for a comic (not just the direct parent), so a shelved
        folder lights up every descendant folder and comic;
        ``reading_list_entries__reading_list`` does the same for a list.

        Models outside :data:`SHELF_MODEL_COLLECTIONS` (search results,
        intermediate querysets) get the no-op. Anonymous sessions and
        shelves the user does not own match nothing.
        """
        if not self._shelf_filter_requested:
            return Q()
        self_collection = SHELF_MODEL_COLLECTIONS.get(model)
        if self_collection is None:
            return Q()
        active = self._active_shelf_collection_codes
        if not active:
            # The filter is on but the user's selected shelves are empty,
            # gone, or not theirs — nothing matches.
            return Q(pk__in=())

        # ``rel`` must be relative to the queryset's model — not the
        # cached ``self.rel_prefix``, which is pinned to the BROWSE
        # model. The browser pipeline runs sub-queries against Comic
        # under collection browses; using the browse-model rel there would
        # produce ``comic__pk`` against Comic and FieldError out.
        rel = self.get_rel_prefix(model)
        subqueries = self._shelf_subqueries
        q = Q()
        for code in sorted(active):
            comic_rel = _SHELF_COLLECTION_COMIC_REL[code]
            q |= Q(**{f"{rel}{comic_rel}__in": subqueries[code]})
        # The row itself is shelved. Covers the rare "shelved collection
        # with no comics yet" case and short-circuits the comic join
        # when the row is its own match.
        self_code = self_collection.value
        if self_code in subqueries:
            q |= Q(pk__in=subqueries[self_code])
        return q

    def get_reading_list_kind_filter(self, model) -> Q:
        """
        Narrow the reading lists grid to curated lists or lists from tags.

        Curated is any list with a source besides tags. ``Exists`` rather
        than a join, so a list's cards and counts are not multiplied by its
        sources, and so cachalot sees the sources table.
        """
        kind = (self.params.get("filters") or {}).get("reading_list_kind")
        if model is not ReadingList or not kind:
            return Q()
        sources = ReadingListSource.objects.filter(reading_list=OuterRef("pk"))
        curated = Exists(sources.exclude(kind=ReadingListSourceKind.TAGS.value))
        if kind == "curated":
            return Q(curated)
        tags = Exists(sources.filter(kind=ReadingListSourceKind.TAGS.value))
        return Q(tags) & ~Q(curated)

    def _get_query_filters(
        self,
        model,
        page_mtime,
        bookmark_filter,
        collection=None,
        pks=None,
        *,
        include_missing=False,
    ) -> Q:
        """Return all the filters except the collection filter."""
        big_include_filter = Q()
        big_exclude_filter = Q()
        big_include_filter &= self.get_acl_filter(
            model, self.request.user, include_missing=include_missing
        )
        big_include_filter &= self.get_collection_filter(
            collection, pks, page_mtime=page_mtime
        )
        big_include_filter &= self.get_comic_field_filter(model)
        if bookmark_filter:
            big_include_filter &= self.get_bookmark_filter(model)
        big_include_filter &= self.get_shelf_filter(model)
        big_include_filter &= self.get_reading_list_kind_filter(model)
        include_search_filter, exclude_search_filter, fts_q = self.get_search_filters(
            model
        )
        big_include_filter &= include_search_filter
        big_exclude_filter &= exclude_search_filter

        return big_include_filter & ~big_exclude_filter & fts_q

    def get_filtered_queryset(
        self,
        model,
        collection=None,
        pks=None,
        *,
        page_mtime=False,
        bookmark_filter=True,
        include_missing=False,
    ) -> QuerySet:
        """
        Get a filtered queryset for the model.

        ``include_missing`` keeps scanner-stamped rows. Only write paths
        and the reader pass it; see ``get_acl_filter``.
        """
        query_filters = self._get_query_filters(
            model,
            page_mtime=page_mtime,
            bookmark_filter=bookmark_filter,
            collection=collection,
            pks=pks,
            include_missing=include_missing,
        )
        qs = model.objects.filter(query_filters)
        # Non-Comic queries traverse ``comic__`` for ACL/group/field filters,
        # which is one-to-many and produces row duplicates that ``.distinct()``
        # must collapse. Comic queries only duplicate when a real m2m relation
        # joins in (story_arc browse, folder browse on cover/choices/bookmark/
        # download targets, or any m2m field filter).
        if model is not Comic or self.comic_filter_uses_m2m:
            qs = qs.distinct()
        return qs
