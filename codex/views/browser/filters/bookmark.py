"""Bookmark filter view methods."""

from django.db.models import Q

from codex.views.bookmark import BookmarkFilterMixin
from codex.views.browser.validate import BrowserValidateView


class BrowserFilterBookmarkView(BookmarkFilterMixin, BrowserValidateView):
    """BookmarkFilter view methods."""

    def __init__(self, *args, **kwargs):
        """Initialize Bookmark Filter."""
        self.init_bookmark_filter()
        super().__init__(*args, **kwargs)

    def get_bookmark_filter(self, model):
        """Build bookmark query."""
        choice: str = self.params.get("filters", {}).get("bookmark", "")
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
