"""Manage user sessions with appropriate defaults."""
from copy import copy
from decimal import Decimal

from django.contrib.sessions.models import Session
from django.db.models import DecimalField
from django.db.models import F
from django.db.models import Q
from django.db.models import Value
from django.db.models.functions import Coalesce

from codex_api.choices.static import DEFAULTS
from codex_api.models import Comic
from codex_api.models import UserBookmark


class SessionMixin:
    """Generic Session Mixin."""

    BROWSE_KEY = "browse"
    READER_KEY = "reader"
    KEYS = (BROWSE_KEY, READER_KEY)

    SESSION_DEFAULTS = {
        BROWSE_KEY: {
            "bookmark_filter": DEFAULTS["bookmarkFilterChoices"],
            "decade_filter": [],
            "characters_filter": [],
            "root_group": DEFAULTS["rootGroupChoices"],
            "sort_by": DEFAULTS["sortChoices"],
            "sort_reverse": False,
            "show": DEFAULTS["show"],
        },
        READER_KEY: {
            "defaults": {"fit_to": DEFAULTS["fitToChoices"], "two_pages": False}
        },
    }

    def get_session(self, session_key):
        """Create or get the view session."""
        data = self.request.session.setdefault(
            session_key, self.SESSION_DEFAULTS[session_key]
        )

        # Set defaults for each key in case they don't exist.
        for key, value in self.SESSION_DEFAULTS[session_key].items():
            data[key] = self.request.session[session_key].setdefault(key, value)
        for key, value in self.SESSION_DEFAULTS[session_key]["show"].items():
            data[key] = self.request.session[session_key]["show"].setdefault(key, value)

        return data


class UserBookmarkMixin:
    """Hold user setting for a comic."""

    def _get_user_bookmark_search_kwargs(self, comic):
        """
        Get the search kwargs for a user's authentication state.

        Comic & Session must be instantiated for create.
        """
        search_kwargs = {"comic": comic}
        if self.request.user.is_authenticated:
            search_kwargs["user"] = self.request.user
        else:
            try:
                session = Session.objects.get(
                    session_key=self.request.session.session_key
                )
            except Session.DoesNotExist:
                self.request.session.save()
                # This save is for first time users to create a session
                # in the db before looking it up.
                session = Session.objects.get(
                    session_key=self.request.session.session_key
                )

            search_kwargs["session"] = session
        return search_kwargs

    def get_user_bookmark(self, pk):
        """Get a user bookmark."""
        comic = Comic.objects.get(pk=pk)
        search_kwargs = self._get_user_bookmark_search_kwargs(comic)
        try:
            ub = UserBookmark.objects.get(**search_kwargs)
        except UserBookmark.DoesNotExist:
            ub = None
        return ub

    def update_user_bookmark(self, updates, pk):
        """Update a user bookmark."""
        comic = Comic.objects.get(pk=pk)
        search_kwargs = self._get_user_bookmark_search_kwargs(comic)
        if updates.get("bookmark") == comic.max_page:
            # Auto finish on bookmark last page
            updates["finished"] = True
        defaults = copy(search_kwargs)
        defaults.update(updates)
        UserBookmark.objects.update_or_create(defaults=defaults, **search_kwargs)

    def get_userbookmark_filter(self, for_comic=False):
        """Get a filter for my session or user defined bookmarks."""
        rel_to_ub = "userbookmark"
        if not for_comic:
            rel_to_ub = "comic__userbookmark"

        if self.request.user.is_authenticated:
            my_bookmarks_kwargs = {f"{rel_to_ub}__user": self.request.user}
        else:
            my_bookmarks_kwargs = {f"{rel_to_ub}__session": self.request.session}
        return Q(**my_bookmarks_kwargs)

    @staticmethod
    def annotate_progress(queryset):
        """Compute progress for each member of a queryset."""
        # Requires bookmark and annotation hoisted from userbookmarks.
        # Requires page_count native to comic or aggregated
        queryset = queryset.annotate(
            progress=Coalesce(
                F("bookmark") * Decimal("1.0") / F("page_count") * 100,
                Value(0.00),
                output_field=DecimalField(),
            )
        )
        return queryset
