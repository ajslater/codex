"""Bookmark filter view methods."""

from django.db.models import Q


class BookmarkFilterMixin:
    """BookmarkFilter view methods."""

    def get_bm_rel(self, model):
        """Create bookmark relation."""
        rel_prefix = self.get_rel_prefix(model)  # type: ignore
        return rel_prefix + "bookmark"

    def get_my_bookmark_filter(self, bm_rel):
        """Get a filter for my session or user defined bookmarks."""
        if self.request.user.is_authenticated:  # type: ignore
            my_bookmarks_kwargs = {f"{bm_rel}__user": self.request.user}  # type: ignore
        else:
            key = f"{bm_rel}__session__session_key"
            my_bookmarks_kwargs = {
                key: self.request.session.session_key  # type: ignore
            }
        return Q(**my_bookmarks_kwargs)

    def get_bookmark_filter(self, model):
        """Build bookmark query."""
        choice = self.params["filters"].get("bookmark", "")  # type: ignore
        if choice:
            bm_rel = self.get_bm_rel(model)
            my_bookmark_filter = self.get_my_bookmark_filter(bm_rel)
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
