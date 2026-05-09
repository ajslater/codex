"""Browser Filters."""

from functools import cached_property
from types import MappingProxyType
from typing import Final

from django.db.models.query import QuerySet
from django.db.models.query_utils import Q

from codex.models import (
    Comic,
    Folder,
    Imprint,
    Publisher,
    Series,
    StoryArc,
    Volume,
)
from codex.models.favorite import Favorite
from codex.views.browser.filters.bookmark import BrowserFilterBookmarkView
from codex.views.const import FOLDER_GROUP, STORY_ARC_GROUP

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
    {"cover", "choices", "bookmark", "download"}
)

# Browser-queryable model → ``Favorite.group`` letter code. Same mapping
# as the API view's `_GROUP_CODE_MODEL_MAP` and the signal-cleanup
# table in ``codex/signals/django_signals.py`` — kept local to avoid a
# circular `codex.models.favorite` ↔ `codex.views` import.
_FAVORITE_MODEL_GROUPS: Final[MappingProxyType[type, str]] = MappingProxyType(
    {
        Publisher: "p",
        Imprint: "i",
        Series: "s",
        Volume: "v",
        Folder: "f",
        StoryArc: "a",
        Comic: "c",
    }
)


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
    def comic_filter_uses_m2m(self) -> bool:
        """
        Return True if the filter pipeline forces an m2m join on Comic.

        Drives whether ``.distinct()`` and the ``search_score`` ``group_by("id")``
        clause need to fire. Non-Comic queries always need them because the
        ACL filter alone traverses ``comic__`` (one-to-many); for Comic
        queries we can skip both unless a real m2m relation joins in.
        """
        group = self.kwargs.get("group")
        pks = self.kwargs.get("pks")
        if pks and 0 not in pks:
            if group == STORY_ARC_GROUP:
                # ``story_arc_numbers__story_arc`` is m2m-through on Comic.
                return True
            if group == FOLDER_GROUP and self.TARGET in _M2M_FOLDER_GROUP_TARGETS:
                # ``folders`` / ``comic__folders`` m2m on these targets.
                return True
        filters = self.params.get("filters") or {}
        return any(filters.get(k) for k in _M2M_FILTER_KEYS)

    def get_favorite_filter(self, model) -> Q:
        """
        Return ``Q(pk__in=<my favorited ids for this group>)`` or ``Q()``.

        Anonymous users always get the no-op — favorites are
        authenticated-only. A model that isn't in
        :data:`_FAVORITE_MODEL_GROUPS` is also a no-op (search results
        and other intermediate querysets aren't favorite-able).
        """
        if not self.params.get("filters", {}).get("favorite"):
            return Q()
        user = self.request.user
        if not user or not user.is_authenticated:
            return Q()
        group_code = _FAVORITE_MODEL_GROUPS.get(model)
        if group_code is None:
            return Q()
        favorited_ids = Favorite.objects.filter(user=user, group=group_code).values(
            "target_id"
        )
        return Q(pk__in=favorited_ids)

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
