"""Bookmark filter view methods."""

from typing import TYPE_CHECKING

from django.db.models import Q

if TYPE_CHECKING:
    from codex.models import BrowserGroupModel


class BookmarkFilterMixin:
    """BookmarkFilter view methods."""

    def init_bookmark_data(self):
        """Initialize the bm_annotation_data."""
        self._bm_annotation_data: dict[BrowserGroupModel, tuple[str, Q]] = {}

    def _get_bm_rel(self, model):
        """Create bookmark relation."""
        rel_prefix = self.get_rel_prefix(model)  # type: ignore
        return rel_prefix + "bookmark"

    def _get_my_bookmark_filter(self, bm_rel):
        """Get a filter for my session or user defined bookmarks."""
        if self.request.user.is_authenticated:  # type: ignore
            my_bookmarks_kwargs = {f"{bm_rel}__user": self.request.user}  # type: ignore
        else:
            key = f"{bm_rel}__session__session_key"
            my_bookmarks_kwargs = {
                key: self.request.session.session_key  # type: ignore
            }
        return Q(**my_bookmarks_kwargs)

    def get_bookmark_rel_and_filter(self, model):
        """Get the bookmark rel and filter once."""
        if model not in self._bm_annotation_data:
            bm_rel = self._get_bm_rel(model)
            bm_filter = self._get_my_bookmark_filter(bm_rel)
            self._bm_annotation_data[model] = (bm_rel, bm_filter)
        return self._bm_annotation_data[model]

    def get_bookmark_filter(self, model):
        """Build bookmark query."""
        choice: str = self.params.get("filters", {}).get("bookmark", "")  # type: ignore
        if choice:
            bm_rel, my_bookmark_filter = self.get_bookmark_rel_and_filter(model)
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
