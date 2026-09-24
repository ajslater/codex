"""Bookmark filter view methods."""

from django.db.models import Q

from codex.views.bookmark import BookmarkFilterMixin
from codex.views.browser.validate import BrowserValidateView


class BrowserFilterBookmarkView(BookmarkFilterMixin, BrowserValidateView):
    """BookmarkFilter view methods."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize Bookmark Filter."""
        self.init_bookmark_filter()
        super().__init__(*args, **kwargs)

    def get_bookmark_filter(self, model):
        """Build bookmark query."""
        choice: str = self.params.get("filters", {}).get("bookmark", "")
        if choice:
            bm_rel = self.get_bm_rel(model)
            my_bookmark_filter = self.get_my_bookmark_filter(bm_rel)
            my_finished_filter = my_bookmark_filter & Q(**{f"{bm_rel}__finished": True})
            if choice == "READ":
                bookmark_filter = my_finished_filter
            elif choice == "UNREAD":
                # UNREAD means "*I* have not finished it" — the negation of
                # my own finished bookmark, including comics I've never
                # opened. Not ``Q(bookmark=None)``, which tests for *any*
                # user's bookmark. Not ``~my_finished_filter`` either:
                # negating a multi-valued ``Q`` compiles each condition to
                # its own EXISTS, so "some bookmark is mine" and "some
                # bookmark is finished" can be two different rows, and
                # another user finishing a comic I'm reading hid it from
                # me. The correlated probe keeps identity and ``finished``
                # in one subquery.
                bookmark_filter = ~Q(self.get_my_finished_bookmark_exists(model))
            else:  # IN_PROGRESS
                bookmark_filter = (
                    my_bookmark_filter
                    & Q(**{f"{bm_rel}__finished__in": (False, None)})
                    & Q(**{f"{bm_rel}__page__gt": 0})
                )
        else:
            bookmark_filter = Q()
        return bookmark_filter
