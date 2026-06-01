"""Browser Filters."""

from functools import cached_property
from typing import Final

from django.db.models.query import QuerySet
from django.db.models.query_utils import Q

from codex.collection import Collection
from codex.models import Comic
from codex.models.favorite import FAVORITE_MODEL_COLLECTIONS, Favorite
from codex.views.browser.filters.bookmark import BrowserFilterBookmarkView
from codex.views.const import FOLDER_COLLECTION, STORY_ARC_COLLECTION

# Active filter keys whose ORM rel crosses an m2m or m2m-through relation
# on Comic. Field-list mirrors ``codex.views.browser.const.BROWSER_FILTER_KEYS``
# minus the local-column / FK keys (year, decade, country, language,
# critical_rating, monochrome, original_format, file_type, reading_direction,
# tagger, age_rating_metron, age_rating_tagged).
_M2M_FILTER_KEYS: Final[frozenset[str]] = frozenset(
    {
        "characters",
        "credits",
        "genres",
        "identifier_source",
        "locations",
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
# Mirrors the branches in :meth:`GroupFilterView._get_rel_for_pks`.
_M2M_FOLDER_GROUP_TARGETS: Final[frozenset[str]] = frozenset(
    {"cover", "choices", "bookmark", "download", "force_update"}
)

# Collection codes whose transitive-favorite clauses introduce m2m JOINs on
# Comic (``folders`` and ``story_arc_numbers__story_arc``). When neither
# code has any favorites the filter Q has no m2m clauses and Comic
# queries don't need ``.distinct()``.
_FAVORITE_M2M_GROUP_CODES: Final[frozenset[str]] = frozenset(
    {Collection.FOLDER, Collection.ARC}
)

# Collection code → comic-side ORM field used to "transitively" match a
# row in that group. ``folders`` and ``story_arc_numbers__story_arc``
# are m2m relations on Comic that carry every ancestor folder / arc,
# so a single favorited folder lights up every descendant comic.
_FAVORITE_COLLECTION_COMIC_REL: Final[dict[str, str]] = {
    Collection.COMIC: "pk",
    Collection.PUBLISHER: "publisher_id",
    Collection.IMPRINT: "imprint_id",
    Collection.SERIES: "series_id",
    Collection.VOLUME: "volume_id",
    Collection.FOLDER: "folders",
    Collection.ARC: "story_arc_numbers__story_arc",
}


class BrowserFilterView(BrowserFilterBookmarkView):
    """Browser Filters."""

    def force_inner_joins(self, qs):
        """Force INNER JOINS to filter empty groups."""
        demote_tables = {"codex_library"}
        if qs.model is not Comic:
            demote_tables.add("codex_comic")
        if self.fts_mode:
            # Forcing INNER JOINS required to make fts5 work
            demote_tables.add("codex_comicfts")
        return qs.demote_joins(demote_tables)

    @cached_property
    def _active_favorite_group_codes(self) -> frozenset[str]:
        """
        Return the groups this user has at least one favorite under.

        One ``DISTINCT`` query per request, cached. Used by
        ``get_favorite_filter`` to skip OR clauses for empty groups
        (which would otherwise force m2m JOINs through ``folders`` and
        ``story_arc_numbers`` on every favorite-filtered request) and
        by ``comic_filter_uses_m2m`` to gate ``.distinct()``.
        """
        if not self.params.get("filters", {}).get("favorite"):
            return frozenset()
        user = self.request.user
        if not user or not user.is_authenticated:
            return frozenset()
        return frozenset(
            Favorite.objects.filter(user=user)
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
        group = self.kwargs.get("collection")
        pks = self.kwargs.get("pks")
        if pks and 0 not in pks:
            if group == STORY_ARC_COLLECTION:
                # ``story_arc_numbers__story_arc`` is m2m-through on Comic.
                return True
            if group == FOLDER_COLLECTION and self.TARGET in _M2M_FOLDER_GROUP_TARGETS:
                # ``folders`` / ``comic__folders`` m2m on these targets.
                return True
        filters = self.params.get("filters") or {}
        if (
            filters.get("favorite")
            and self._active_favorite_group_codes & _FAVORITE_M2M_GROUP_CODES
        ):
            # The transitive favorites Q only introduces m2m clauses
            # for groups the user has actually favorited under. With
            # zero folder / arc favorites the Q stays on direct fields
            # and Comic queries don't need ``.distinct()``.
            return True
        return any(filters.get(k) for k in _M2M_FILTER_KEYS)

    @cached_property
    def _favorite_subqueries(self):
        """Per-group favorited-id subqueries, materialized once per request."""
        user = self.request.user
        return {
            code: Favorite.objects.filter(user=user, collection=code).values(
                "target_id"
            )
            for code in self._active_favorite_group_codes
        }

    def get_favorite_filter(self, model) -> Q:
        """
        Return a transitive Q for the "favorites only" filter, or ``Q()``.

        Hierarchical: a row passes if itself, an ancestor, or a
        descendant in the comic chain is favorited. That keeps the
        filter behaving like a "navigation tree of starred items" —
        starring a Publisher narrows to its full subtree (so the user
        can drill down to the comic), and starring a Comic keeps every
        ancestor (Publisher → Series → Volume → Comic) reachable.

        Each OR clause traces ``rel_prefix + comic_field`` to a
        per-group favorited-id subquery, but only for groups the user
        has actually favorited under (see
        :attr:`_active_favorite_group_codes`). That keeps the m2m
        ``folders`` / ``story_arc_numbers__story_arc`` JOINs out of
        the SQL when no folder / arc favorites exist — typically the
        common case. ``folders`` is the m2m of every ancestor folder
        for a comic (not just the direct parent), so a favorited
        folder lights up every descendant folder and comic;
        ``story_arc_numbers__story_arc`` is the analogous m2m-through
        to StoryArc.

        Anonymous users and models outside
        :data:`FAVORITE_MODEL_COLLECTIONS` (search results, intermediate
        querysets) get the no-op.
        """
        if not self.params.get("filters", {}).get("favorite"):
            return Q()
        if FAVORITE_MODEL_COLLECTIONS.get(model) is None:
            return Q()
        active = self._active_favorite_group_codes
        if not active:
            # User has the filter on but zero favorites — nothing matches.
            return Q(pk__in=())

        # ``rel`` must be relative to the queryset's model — not the
        # cached ``self.rel_prefix``, which is pinned to the BROWSE
        # model. The browser pipeline runs sub-queries against Comic
        # under group browses; using the browse-model rel there would
        # produce ``comic__pk`` against Comic and FieldError out.
        rel = self.get_rel_prefix(model)
        subqueries = self._favorite_subqueries
        q = Q()
        for code in active:
            comic_rel = _FAVORITE_COLLECTION_COMIC_REL[code]
            q |= Q(**{f"{rel}{comic_rel}__in": subqueries[code]})
        # The row itself is starred. Covers the rare "favorited group
        # with no comics yet" case and short-circuits the comic join
        # when the row is its own match.
        self_code = FAVORITE_MODEL_COLLECTIONS[model]
        if self_code in subqueries:
            q |= Q(pk__in=subqueries[self_code])
        return q

    def _get_query_filters(
        self,
        model,
        page_mtime,
        bookmark_filter,
        group=None,
        pks=None,
    ) -> Q:
        """Return all the filters except the group filter."""
        big_include_filter = Q()
        big_exclude_filter = Q()
        big_include_filter &= self.get_acl_filter(model, self.request.user)
        big_include_filter &= self.get_group_filter(group, pks, page_mtime=page_mtime)
        big_include_filter &= self.get_comic_field_filter(model)
        if bookmark_filter:
            big_include_filter &= self.get_bookmark_filter(model)
        big_include_filter &= self.get_favorite_filter(model)
        include_search_filter, exclude_search_filter, fts_q = self.get_search_filters(
            model
        )
        big_include_filter &= include_search_filter
        big_exclude_filter &= exclude_search_filter

        return big_include_filter & ~big_exclude_filter & fts_q

    def get_filtered_queryset(
        self,
        model,
        group=None,
        pks=None,
        *,
        page_mtime=False,
        bookmark_filter=True,
    ) -> QuerySet:
        """Get a filtered queryset for the model."""
        query_filters = self._get_query_filters(
            model,
            page_mtime=page_mtime,
            bookmark_filter=bookmark_filter,
            group=group,
            pks=pks,
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
