"""Manage user sessions with appropriate defaults."""
from copy import copy

from django.contrib.sessions.models import Session

from codex.forms import BookmarkFilterChoice
from codex.forms import FitToChoice
from codex.forms import SortChoice
from codex.models import Comic
from codex.models import UserBookmark


class SessionMixin:
    """Generic Session Mixin."""

    BROWSE_KEY = "browse"
    READER_KEY = "reader"
    KEYS = (BROWSE_KEY, READER_KEY)

    SESSION_DEFAULTS = {
        BROWSE_KEY: {
            "bookmark_filter": BookmarkFilterChoice.ALL.name,
            "decade_filter": [],
            "character_filter": [],
            "root_group": "s",
            "sort_by": SortChoice.sort_name.name,
            "sort_reverse": False,
            "settings": {"show_publishers": False, "show_series": False},
        },
        READER_KEY: {
            "group": "r",
            "pk": 0,
            "fit_to": FitToChoice.WIDTH.name,
            "two_pages": False,
        },
    }

    def get_session(self, session_key):
        """Create or get the view session."""
        return self.request.session.setdefault(
            session_key, self.SESSION_DEFAULTS[session_key]
        )

    def session_get(self, session_key, key, form=None):
        """Get a value from form, session, or default and write it back."""
        session = self.get_session(session_key)
        val = None
        if form:
            val = form.cleaned_data.get(key)
        if val is None:
            val = session.get(key)
        if val is None:
            val = self.SESSION_DEFAULTS[session_key][key]
        session[key] = val
        return val

    def session_form_set(self, session_key, form):
        """Get all the session keys and write them back."""
        if session_key == self.READER_KEY and not form.cleaned_data.get("make_default"):
            del form.cleaned_data["fit_to"]
            del form.cleaned_data["two_pages"]
        for key in self.SESSION_DEFAULTS[session_key].keys():
            self.session_get(session_key, key, form)


class UserBookmarkMixin:
    """Hold user setting for a comic."""

    def _get_user_bookmark_search_kwargs(self, pk):
        """
        Get the search kwargs for a user's authentication state.

        Comic & Session must be instantiated for create.
        """
        comic = Comic.objects.get(pk=pk)
        search_kwargs = {"comic": comic}
        if self.request.user.is_authenticated:
            search_kwargs["user"] = self.request.user
        else:
            session = Session.objects.get(session_key=self.request.session.session_key)
            search_kwargs["session"] = session
        return search_kwargs

    def get_user_bookmark(self, pk):
        """Get a user bookmark."""
        search_kwargs = self._get_user_bookmark_search_kwargs(pk)
        try:
            ub = UserBookmark.objects.get(**search_kwargs)
        except UserBookmark.DoesNotExist:
            ub = None
        return ub

    def update_user_bookmark(self, updates, pk):
        """Update a user bookmark."""
        search_kwargs = self._get_user_bookmark_search_kwargs(pk)
        defaults = copy(search_kwargs)
        defaults.update(updates)
        UserBookmark.objects.update_or_create(defaults=defaults, **search_kwargs)
