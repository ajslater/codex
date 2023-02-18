"""Bookmark filter view methods."""
from django.db.models import Q

from codex.serializers.choices import CHOICES


class BookmarkFilterMixin:
    """BookmarkFilter view methods."""

    _BOOKMARK_FILTERS = frozenset(set(CHOICES["bookmarkFilter"].keys()) - {"ALL"})

    def get_bm_rel(self, is_model_comic):
        """Create bookmark relation."""
        bm_rel = "bookmark"
        if not is_model_comic:
            bm_rel = "comic__" + bm_rel
        return bm_rel

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

    def get_bookmark_filter(self, is_model_comic, choice):
        """Build bookmark query."""
        if choice is None:
            choice = self.params["filters"].get("bookmark", "ALL")  # type: ignore
        if choice in self._BOOKMARK_FILTERS:
            bm_rel = self.get_bm_rel(is_model_comic)
            my_bookmark_filter = self._get_my_bookmark_filter(bm_rel)
            if choice in ("UNREAD", "IN_PROGRESS"):
                my_not_finished_filter = my_bookmark_filter & Q(
                    **{f"{bm_rel}__finished__in": (False, None)}
                )
                if choice == "UNREAD":
                    bookmark_filter = Q(**{bm_rel: None}) | my_not_finished_filter
                else:  # IN_PROGRESS
                    bookmark_filter = my_not_finished_filter & Q(
                        **{f"{bm_rel}__page__gt": 0}
                    )
            else:  # READ
                bookmark_filter = my_bookmark_filter & Q(
                    **{f"{bm_rel}__finished": True}
                )
        else:
            bookmark_filter = Q()
        return bookmark_filter
