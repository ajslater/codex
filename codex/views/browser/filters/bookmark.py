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
        if not choice:
            return Q()
        if choice == "UNREAD":
            # "I have no finished bookmark on this comic." The old
            # ``Q(bookmark=None) | my-unfinished`` pair was wrong in
            # multi-user installs: ``bookmark=None`` matches only comics
            # with no bookmark from ANY user or session, so a comic
            # finished by someone else matched neither arm and silently
            # vanished from my unread listing.
            return ~Q(self.get_my_finished_bookmark_exists(model))
        bm_rel = self.get_bm_rel(model)
        my_bookmark_filter = self.get_my_bookmark_filter(bm_rel)
        if choice == "READ":
            return my_bookmark_filter & Q(**{f"{bm_rel}__finished": True})
        # IN_PROGRESS
        return (
            my_bookmark_filter
            & Q(**{f"{bm_rel}__finished__in": (False, None)})
            & Q(**{f"{bm_rel}__page__gt": 0})
        )
