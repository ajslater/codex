"""Browser Filters."""

from collections.abc import Collection
from functools import cached_property
from typing import Final

from django.db.models.query import QuerySet
from django.db.models.query_utils import Q

from codex.models import Comic, ReadingList
from codex.views.browser.filters.bookmark import BrowserFilterBookmarkView
from codex.views.browser.filters.reading_lists import (
    READING_LIST_KIND_FILTER,
    RETIRED_SHELVES_FILTER,
)
from codex.views.const import FOLDER_COLLECTION, STORY_ARC_COLLECTION
from codex.views.readinglists.access import list_kind_q

# TARGETs whose folder-group filter resolves to ``folders`` (m2m) or
# ``comic__folders`` (download) rather than ``parent_folder`` (FK).
# Mirrors the branches in :meth:`CollectionFilterView._get_rel_for_pks`.
_M2M_FOLDER_GROUP_TARGETS: Final[frozenset[str]] = frozenset(
    {"cover", "choices", "bookmark", "download", "force_update"}
)


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
    def comic_filter_uses_m2m(self) -> bool:
        """
        Return True if the filter pipeline forces an m2m join on Comic.

        Drives whether ``.distinct()`` and the ``search_score`` ``group_by("id")``
        clause need to fire. Non-Comic queries always need them because the
        ACL filter alone traverses ``comic__`` (one-to-many); for Comic
        queries we can skip both unless a real m2m relation joins in. A tag
        filter never does: it tests membership with an ``IN`` subquery (see
        ``ComicFieldFilterView._filter_by_comic_field``).
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
        return False

    def get_retired_filter(self) -> Q:
        """
        Match nothing for a request still filtering by a shelf.

        Shelves folded into reading lists; their filter is retired. A
        client that still sends it gets an empty page, not the whole
        library it would get if the key were ignored.
        """
        if (self.params.get("filters") or {}).get(RETIRED_SHELVES_FILTER):
            return Q(pk__in=())
        return Q()

    def get_reading_list_kind_filter(self, model, collection=None, pks=None) -> Q:
        """
        Narrow the grid of lists to the picked kinds; see ``list_kind_q``.

        Several kinds show a list of any of them. One list opens whole
        whatever kind is picked.
        """
        kinds = (self.params.get("filters") or {}).get(READING_LIST_KIND_FILTER)
        if not kinds or not self.is_lists_grid(model, collection, pks):
            return Q()
        return list_kind_q(kinds, self.request.user)

    def _get_query_filters(
        self,
        model,
        page_mtime,
        bookmark_filter,
        collection=None,
        pks=None,
        *,
        include_missing=False,
        omit: Collection[str] = (),
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
        big_include_filter &= self.get_comic_field_filter(
            model, collection, pks, omit=omit
        )
        if bookmark_filter:
            big_include_filter &= self.get_bookmark_filter(model)
        big_include_filter &= self.get_retired_filter()
        if READING_LIST_KIND_FILTER not in omit:
            big_include_filter &= self.get_reading_list_kind_filter(
                model, collection, pks
            )
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
        omit: Collection[str] = (),
    ) -> QuerySet:
        """
        Get a filtered queryset for the model.

        ``include_missing`` keeps scanner-stamped rows. Only write paths
        and the reader pass it; see ``get_acl_filter``. ``omit`` names
        filters to leave out, as a filter's own choices do.
        """
        query_filters = self._get_query_filters(
            model,
            page_mtime=page_mtime,
            bookmark_filter=bookmark_filter,
            collection=collection,
            pks=pks,
            include_missing=include_missing,
            omit=omit,
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
