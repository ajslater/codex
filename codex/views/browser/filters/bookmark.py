"""Bookmark filter view methods."""

from typing import TYPE_CHECKING

from django.db.models import Q

from codex.views.browser.validate import BrowserValidateView

if TYPE_CHECKING:
    from codex.models import BrowserGroupModel


class BrowserFilterBookmarkView(BrowserValidateView):
    """BookmarkFilter view methods."""

    def __init__(self, *args, **kwargs):
        """Initialize the bm_annotation_data."""
        super().__init__(*args, **kwargs)
        self._bm_rels: dict[BrowserGroupModel, str] = {}
        self._bm_filters: dict[BrowserGroupModel, Q] = {}

    def _get_bm_rel(self, model):
        """Create bookmark relation."""
        if model not in self._bm_rels:
            rel_prefix = self.get_rel_prefix(model)  # type: ignore
            self._bm_rels[model] = rel_prefix + "bookmark"
        return self._bm_rels[model]

    def _get_my_bookmark_filter(self, bm_rel):
        """Get a filter for my session or user defined bookmarks."""
        if self.request.user and self.request.user.is_authenticated:
            key = f"{bm_rel}__user"
            value = self.request.user
        else:
            key = f"{bm_rel}__session__session_key"
            value = self.request.session.session_key
        my_bookmarks_kwargs = {key: value}
        return Q(**my_bookmarks_kwargs)

    def get_bookmark_filter(self, model):
        """Build bookmark query."""
        choice: str = self.params.get("filters", {}).get("bookmark", "")  # type: ignore
        if choice:
            bm_rel = self._get_bm_rel(model)
            my_bookmark_filter = self._get_my_bookmark_filter(bm_rel)
            if choice == "READ":
                bookmark_filter = my_bookmark_filter & Q(
                    **{f"{bm_rel}__finished": True}
                )
            else:
                my_not_finished_filter = my_bookmark_filter & Q(
                    **{f"{bm_rel}__finished__in": (False, None)}
                )
                if choice == "UNREAD":
                    bookmark_filter = Q(**{bm_rel: None}) | my_not_finished_filter
                else:  # IN_PROGRESS
                    bookmark_filter = my_not_finished_filter & Q(
                        **{f"{bm_rel}__page__gt": 0}
                    )
        else:
            bookmark_filter = Q()
        return bookmark_filter
